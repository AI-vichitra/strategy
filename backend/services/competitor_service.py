"""
Competitor Resolver Service
============================
Hybrid competitor-discovery engine: context-driven Tavily search -> LLM
resolution -> Firecrawl verification. Produces trustworthy, auditable
competitor entries instead of the legacy domain-frequency heuristic.

Three layers, each doing one job:
  1. Tavily  (web_scrapper.tavily_comp.search_candidates) -> finds raw
     article/search results about the brand's competitive space.
  2. LLM + Tavily, two-pass (resolve_competitors, below):
       Pass 1 - the LLM extracts competitor NAMES ONLY from the raw
       article/snippet content (never a URL at this stage, so there is
       nothing for it to fabricate a link for).
       Pass 2 - a dedicated Tavily lookup per extracted name resolves that
       company's own official URL via a domain/name-match heuristic. A name
       with no resolvable URL still survives with website_url="" rather
       than being dropped.
  3. Firecrawl (verify_competitors, below) -> for candidates that DO have a
     URL, proves it's actually live (verified=True/dropped on failure);
     candidates with no URL pass through unverified (verified=False)
     without a scrape attempt, since there is nothing to fetch.

Gated behind the COMPETITOR_LLM_RESOLVER env flag in tavily_service.py.

Top-up model: user-provided competitors are always kept and ranked first;
auto-discovery tops up the remaining gap toward MAX_SUGGESTIONS, a larger
suggestion pool than the MAX_COMPETITORS selection cap the frontend enforces
(see discover_and_resolve). discover_and_resolve raises CompetitorDiscoveryFailure
when the pipeline could not run at all (distinct from a legitimate empty
result) — on the ON path, tavily_service.search_competitors never falls back
to the legacy heuristic for either case, only for the flag being OFF.
resolve_competitors itself still returns None as its own internal "caller
must treat this as a failure" signal, consumed only by discover_and_resolve.
"""

import json
import logging
import os
import re
import sys
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# web_scrapper/ sits at the project root, alongside backend/ — not importable
# as a package without the project root on sys.path. Done once at module load
# (idempotent) so both the CompetitorDiscoveryFailure re-export below and
# discover_and_resolve's own later `from web_scrapper import tavily_comp` work.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Re-exported from tavily_comp (not defined here) so that module — which also
# has a standalone CLI entry point — never needs backend's package path on
# sys.path at its own import time. Raised by discover_and_resolve (via
# tavily_comp.search_candidates) when the hybrid pipeline could not run at
# all: missing TAVILY_API_KEY, the Tavily call raising/returning a malformed
# shape or every per-query call failing, no LLM provider key, or an
# unparseable LLM response. Deliberately distinct from a legitimate empty
# result (which returns normally) — callers must catch this and fall back to
# the user-provided competitors only, with discovery_status="failed", never
# to the legacy heuristic.
from web_scrapper.tavily_comp import CompetitorDiscoveryFailure  # noqa: E402

# MIN/MAX_COMPETITORS bound the CONFIRMED selection the user makes from the
# suggestion list — enforced on the frontend (hard gate), never here.
MIN_COMPETITORS = 3
MAX_COMPETITORS = 5

# MAX_SUGGESTIONS bounds the raw SUGGESTION pool this module hands to the
# frontend (user-provided entries first, auto-discovered top up the rest),
# which the frontend then lets the user select up to MAX_COMPETITORS from.
# Deliberately larger than MAX_COMPETITORS and never clamped to it here.
MAX_SUGGESTIONS = 8

REFERENCE_CONTEXT_CHAR_CAP = 2000
MAX_LLM_RESPONSE_CHARS = 20_000


# ── URL helpers ───────────────────────────────────────────────────────────────
def _normalize_host(url: str) -> str:
    """Lower-cased host with a leading 'www.' stripped, for host-to-host
    grounding/dedup comparisons. Empty string for an unparseable url."""
    if not url:
        return ""
    u = url if url.startswith("http") else f"https://{url}"
    netloc = urlparse(u).netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc


def _normalize_website_url(url: str) -> str:
    """Normalizes to scheme+host only — query/tracking params and path are
    stripped, per the design decision that website_url is a clean root link."""
    u = url if url.startswith("http") else f"https://{url}"
    p = urlparse(u)
    if not p.netloc:
        return url
    return f"{p.scheme or 'https'}://{p.netloc}"


# ── Brand-identity context from uploaded reference docs ─────────────────────
def _build_brand_context(reference_ref_ids: Optional[List[str]]) -> str:
    """Loads each reference doc's extracted text (reference_service), capped
    to ~2k chars TOTAL across all of them, as a brand-identity signal to help
    the LLM judge same-vertical relevance. Never a source of competitor
    names/URLs itself."""
    if not reference_ref_ids:
        return ""
    from backend.services import reference_service

    parts: List[str] = []
    remaining = REFERENCE_CONTEXT_CHAR_CAP
    for ref_id in reference_ref_ids:
        if remaining <= 0:
            break
        text = reference_service.load_reference_text(ref_id)
        if not text:
            continue
        chunk = text[:remaining]
        parts.append(chunk)
        remaining -= len(chunk)
    return "\n\n".join(parts)


# ── Strict JSON parsing of the LLM response ──────────────────────────────────
def _extract_json_array(text: str) -> Optional[List[Any]]:
    """Returns a parsed JSON list, or None if the text isn't one (including
    when it's missing, oversized, or merely contains a JSON-looking fragment
    that doesn't parse) — per spec, malformed/oversized JSON means full
    fallback, never a partial best-effort parse."""
    if not text:
        return None
    if len(text) > MAX_LLM_RESPONSE_CHARS:
        logger.warning("[CompetitorService] LLM response exceeded size cap — treating as malformed.")
        return None

    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
        cleaned = re.sub(r"```\s*$", "", cleaned).strip()

    try:
        data = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        match = re.search(r"\[.*\]", cleaned, re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except (json.JSONDecodeError, ValueError):
            return None

    return data if isinstance(data, list) else None


# ── Step 2a: two-pass LLM resolution (names from articles, URLs from a
#    dedicated per-name lookup) — replaces the old single-pass+grounding
#    approach, which asked the LLM to extract {name, website_url} directly
#    from Tavily's article results and then dropped every item via a host-
#    match grounding check against those SAME article URLs. That grounding
#    rule was correct but useless: article/news/directory URLs (e.g.
#    yourstory.com, tracxn.com) never match a competitor's own domain (e.g.
#    dabur.com), so genuine competitors were always discarded. ─────────────
def resolve_competitors(
    raw_results: List[Dict[str, Any]],
    brand_name: str,
    category: str,
    region: Optional[str],
    brand_context: Optional[str],
    user_competitors: Optional[List[Dict[str, Any]]],
    industry: Optional[str] = None,
    product_focus: Optional[str] = None,
) -> Optional[List[Dict[str, Any]]]:
    """
    Two-pass resolution of Tavily's raw structured (article) results into
    clean {name, website_url, source_url, summary} competitor entries.

    Pass 1 — LLM extracts competitor brand NAMES ONLY from the article
    content (title/snippet). Trustworthy because it never fabricates a URL.
    Pass 2 — a dedicated Tavily lookup per extracted name
    ("{name} official website {product_focus}") finds that company's own
    domain, picked via a same-name-in-domain heuristic that excludes known
    non-company domains (social/wiki/corporate-registry sites). A name Pass 2
    can't resolve still survives with website_url="" (never None — see
    verify_competitors()'s two branches: with no Firecrawl key configured it
    is kept, marked verified=False; WITH a Firecrawl key configured,
    firecrawl_service.scrape_url("", key) returns None immediately and
    verify_competitors silently drops it — a known gap, since this function
    cannot and does not touch verify_competitors itself to special-case that).

    Returns None (caller must fall back to legacy logic) when:
      - no LLM provider key is configured at all, or
      - the LLM's Pass-1 response can't be parsed as a JSON array.
    Returns [] (a valid, non-fallback result) when Pass 1 legitimately
    extracts zero competitor names, or dedup removes everything.
    """
    from backend.services.ai_service import _get_llm_provider

    try:
        _get_llm_provider()
    except RuntimeError:
        return None

    if not raw_results:
        return []

    focus = product_focus or industry or category

    # ── Pass 1: extract competitor NAMES ONLY from the article content ──────
    results_block = "\n".join(
        f"{i + 1}. title: {r.get('title', '')}\n"
        f"   snippet: {(r.get('snippet') or r.get('content') or '')[:400]}"
        for i, r in enumerate(raw_results)
    )

    context_clause = (
        f"\n\nAdditional brand-identity context (from the brand's own uploaded "
        f"reference documents — use ONLY to judge same-vertical relevance, "
        f"NEVER as a source of competitor names):\n{brand_context}"
        if brand_context
        else ""
    )

    system_prompt = (
        f"From the following search results about {brand_name} in the {focus} space, "
        f"extract up to 8 competitor brand names. These are companies that compete "
        f"directly with {brand_name} in {focus}.\n\n"
        "Return a JSON array of objects with ONLY the 'name' field:\n"
        '[{"name": "Dabur"}, {"name": "Patanjali"}]\n\n'
        "Rules:\n"
        "- Extract names mentioned in article titles, snippets and content as competitors or alternatives\n"
        f"- Do NOT include {brand_name} itself\n"
        "- Do NOT include market research firms, directories, or news sites\n"
        "- Do NOT fabricate names — only extract names explicitly mentioned in the provided content\n"
        f"- This brand operates in: {focus}. Only include competitors in the same or directly adjacent product space.\n"
        "- Return ONLY the JSON array, nothing else."
        f"{context_clause}"
    )
    user_prompt = f"Raw search results:\n{results_block}"

    from backend.services.slide_planner import _default_llm_completion

    print(f"[COMP-RESOLVE] LLM prompt length: {len(user_prompt)} chars")

    try:
        raw_text = _default_llm_completion(system_prompt, user_prompt)
    except Exception as e:
        logger.warning(f"[CompetitorService] LLM resolution call failed: {e}")
        return None

    print(f"[COMP-RESOLVE] LLM raw response: {(raw_text or '')[:500]}")

    parsed = _extract_json_array(raw_text)
    if parsed is None:
        logger.warning("[CompetitorService] LLM response was not a parseable JSON array — full fallback.")
        return None

    print(f"[COMP-RESOLVE] Parsed {len(parsed)} candidates from LLM")

    brand_name_lower = brand_name.strip().lower()
    names: List[str] = []
    seen_names_lower = set()
    for item in parsed:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        lname = name.lower()
        if lname == brand_name_lower or lname in seen_names_lower:
            continue
        seen_names_lower.add(lname)
        names.append(name)

    print(f"[COMP-RESOLVE] Pass 1 — extracted {len(names)} competitor names: {names}")

    if not names:
        return []

    # ── Pass 2: resolve each name to its own official URL via a dedicated
    #    Tavily lookup — never reuses/requires the Pass-1 article URLs. ──────
    _EXCLUDED_URL_DOMAINS = (
        "linkedin.com", "facebook.com", "twitter.com", "instagram.com", "youtube.com",
        "wikipedia.org", "crunchbase.com", "tracxn.com", "zaubacorp.com", "tofler.in",
    )

    def _simplify(s: str) -> str:
        return re.sub(r"[^a-z0-9]", "", s.lower())

    tavily_api_key = os.environ.get("TAVILY_API_KEY")
    pass2_client = None
    if tavily_api_key:
        try:
            from tavily import TavilyClient
            pass2_client = TavilyClient(api_key=tavily_api_key)
        except Exception as e:
            logger.warning(f"[CompetitorService] Pass 2 TavilyClient init failed: {e}")
            pass2_client = None

    def _resolve_pass2_url(name: str) -> str:
        if pass2_client is None:
            return ""
        try:
            resp = pass2_client.search(
                query=f"{name} official website {focus}",
                search_depth="basic",
                max_results=3,
            )
        except Exception as e:
            logger.warning(f"[CompetitorService] Pass 2 Tavily lookup failed for '{name}': {e}")
            return ""

        simplified_name = _simplify(name)
        for r in (resp.get("results", []) or []):
            url = r.get("url", "")
            if not url:
                continue
            domain = urlparse(url).netloc.lower().replace("www.", "")
            if any(d in domain for d in _EXCLUDED_URL_DOMAINS):
                continue
            domain_root = _simplify(domain.split(".")[0])
            if simplified_name and (simplified_name in domain_root or domain_root in simplified_name):
                return _normalize_website_url(url)
        return ""

    def _find_source_article_url(name: str) -> str:
        """Best-effort trace-back to whichever Pass-1 article first mentions
        this name, for source_url only — Pass 1's prompt only asks the LLM
        for names, not a name-to-article mapping, so this is a substring-match
        heuristic, not a guaranteed-exact attribution. Deliberately does NOT
        surface the article's raw snippet as a "summary": that snippet is
        unfiltered Tavily article content (can itself be a markdown table, a
        listicle heading like "## List of Packaged Honey Companies", etc.) —
        not something safe to show on a competitor card, and nothing
        downstream of this module's return value consumes a summary field, so
        it's left blank rather than risk surfacing that junk."""
        lname = name.lower()
        for r in raw_results:
            title = r.get("title", "") or ""
            snippet = r.get("snippet") or r.get("content") or ""
            if lname in title.lower() or lname in snippet.lower():
                return r.get("url", "")
        return ""

    candidates: List[Dict[str, Any]] = []
    for name in names:
        url = _resolve_pass2_url(name)
        print(f"[COMP-RESOLVE] Pass 2 — '{name}' → {url or 'no URL found'}")
        candidates.append({
            "name": name,
            "website_url": url,  # "" (never None) when unresolved — see docstring
            "source_url": _find_source_article_url(name),
            "summary": "",
        })

    # ── Dedup against user-provided competitors (same company/url collapses;
    #    the user's own entry wins, so the resolved duplicate is dropped here —
    #    the caller appends the user's entries separately). ───────────────────
    if user_competitors:
        user_hosts = {_normalize_host(uc.get("url", "")) for uc in user_competitors if uc.get("url")}
        user_hosts.discard("")
        user_names = {uc["name"].strip().lower() for uc in user_competitors if uc.get("name")}

        candidates = [
            item for item in candidates
            if _normalize_host(item["website_url"]) not in user_hosts
            and item["name"].strip().lower() not in user_names
        ]

    return candidates[:MAX_SUGGESTIONS]


# ── Step 2b: Firecrawl verification ──────────────────────────────────────────
def verify_competitors(
    resolved: List[Dict[str, Any]],
    firecrawl_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Best-effort Firecrawl verification that each candidate URL is actually
    live. Verification is best-effort and never BLOCKS the feature:
      - no Firecrawl key -> skip verification entirely, return the input
        unchanged with verified=False on each (nothing dropped for lack of a key).
      - with a key -> scrape each of up to MAX_SUGGESTIONS urls,
        sequentially (mirrors pipeline_service's existing Firecrawl usage);
        live/non-empty content -> verified=True; dead/empty/error -> DROP
        (a dead URL is exactly the untrustworthy result this exists to catch).
      - a candidate with no website_url (Pass 2 of resolve_competitors found
        no resolvable URL for that name) is never scraped — there is nothing
        to fetch — and passes through unconditionally with verified=False,
        in both the no-key and has-key branches.
    """
    print(f"[COMP-VERIFY] Verifying {len(resolved)} candidates with Firecrawl")

    if not firecrawl_key:
        return [{**item, "verified": False} for item in resolved]

    from backend.services import firecrawl_service

    verified: List[Dict[str, Any]] = []
    for item in resolved[:MAX_SUGGESTIONS]:
        website_url = item.get("website_url") or ""
        if not website_url:
            print(f"[COMP-VERIFY] '{item.get('name', '')}' has no URL — skipping Firecrawl, marked unverified")
            verified.append({**item, "verified": False})
            continue

        content = None
        try:
            content = firecrawl_service.scrape_url(website_url, firecrawl_key)
        except Exception as e:
            logger.warning(
                f"[CompetitorService] Firecrawl verification failed for "
                f"{website_url}: {e}"
            )
            content = None

        if content:
            verified.append({**item, "verified": True})
        # else: drop silently — dead/empty/error result, not a trustworthy competitor.

    return verified


# ── Top-up / merge model ───────────────────────────────────────────────────────
def _user_competitors_to_candidates(user_competitors: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """User entries in the plain {name, website_url} shape — no source_url/
    summary/verified, which is exactly how the caller (tavily_service) tells
    a user-provided entry apart from an auto-discovered one."""
    if not user_competitors:
        return []
    return [
        {"name": uc["name"], "website_url": uc.get("url") or uc.get("website_url") or ""}
        for uc in user_competitors if uc.get("name")
    ]


def _merge_user_and_auto(
    user_as_candidates: List[Dict[str, Any]], auto_filled: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """User entries first (always kept, ranked first, never capped away),
    then the auto-discovered top-up. auto_filled is expected to already be
    deduped against the user list and capped to auto_target by the caller."""
    return user_as_candidates + auto_filled


# ── Orchestration ─────────────────────────────────────────────────────────────
def discover_and_resolve(
    brand_name: str,
    website_url: str,
    category: str,
    industry: Optional[str] = None,
    region: Optional[str] = None,
    user_competitors: Optional[List[Dict[str, Any]]] = None,
    reference_ref_ids: Optional[List[str]] = None,
    firecrawl_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Ties Step 1 (Tavily structured search) -> Step 2a (LLM resolve + grounding)
    -> Step 2b (Firecrawl verify) together, then applies the top-up/merge
    model: user-provided competitors are always kept and ranked first;
    auto-discovery tops up the gap toward MAX_SUGGESTIONS, a larger pool than
    MAX_COMPETITORS (auto_target = max(0, MAX_SUGGESTIONS - len(user_competitors))).
    This returns a SUGGESTION pool for the frontend to select from — the
    frontend, not this function, enforces the MAX_COMPETITORS (5) selection
    cap and MIN_COMPETITORS (3) confirm gate.

    Returns {"status": "ok" | "empty", "candidates": [...]}:
      - "candidates" is always the FINAL merged list (user entries first),
        up to MAX_SUGGESTIONS long.
      - "empty" means auto-discovery contributed nothing — either Tavily's
        call succeeded but found zero raw candidates, or grounding/dedup/
        verification attrition left zero survivors. In both cases this is a
        legitimate, trusted result (not a failure): "candidates" is then
        just the user-provided list, which may itself be [].
      - "ok" means either auto_target was already 0 (user alone already
        provided MAX_SUGGESTIONS competitors, so no discovery was even
        attempted) or at least one auto-discovered competitor survived the
        full pipeline.

    Raises CompetitorDiscoveryFailure when the pipeline could not run at all
    (missing TAVILY_API_KEY, the Tavily call raising/returning a malformed
    shape, no LLM key, or an unparseable LLM response) — callers must catch
    this and fall back to the user-provided competitors only, status
    "failed", NEVER to the legacy domain-frequency heuristic.
    """
    user_as_candidates = _user_competitors_to_candidates(user_competitors)

    auto_target = max(0, MAX_SUGGESTIONS - len(user_as_candidates))
    if auto_target == 0:
        # User alone already fills every slot — no discovery needed, and
        # nothing failed, so this is a trivial success, not "empty".
        return {"status": "ok", "candidates": user_as_candidates}

    from web_scrapper import tavily_comp

    if not os.environ.get("TAVILY_API_KEY"):
        raise CompetitorDiscoveryFailure("TAVILY_API_KEY not configured")

    try:
        raw = tavily_comp.search_candidates(
            brand_name, website_url, category, industry=industry, region=region
        )
    except CompetitorDiscoveryFailure:
        raise  # already the right type/message (e.g. "All Tavily search queries failed") — don't rewrap
    except Exception as e:
        raise CompetitorDiscoveryFailure(f"Tavily structured search raised: {e}") from e

    if not isinstance(raw, dict) or "results" not in raw:
        raise CompetitorDiscoveryFailure("Tavily structured search returned a malformed shape")

    raw_results = raw["results"]
    product_focus = raw.get("product_focus") or category
    print(f"[COMP-RESOLVE] Received {len(raw_results)} candidates from search, product_focus='{product_focus}'")

    if not raw_results:
        print("[COMP-RESOLVE] No raw candidates from Tavily — returning empty")
        # Tavily's call succeeded; it genuinely found zero raw candidates —
        # a trusted empty result, not a failure.
        return {"status": "empty", "candidates": user_as_candidates}

    brand_context = _build_brand_context(reference_ref_ids)

    resolved = resolve_competitors(
        raw_results=raw_results,
        brand_name=brand_name,
        category=category,
        region=region,
        brand_context=brand_context,
        user_competitors=user_competitors,
        industry=industry,
        product_focus=product_focus,
    )
    if resolved is None:
        raise CompetitorDiscoveryFailure("LLM resolution unavailable or returned an unparseable response")

    verified = verify_competitors(resolved, firecrawl_key=firecrawl_key)
    # Attrition already happened above (denylist in tavily_comp, dedup in
    # resolve_competitors, liveness in verify_competitors) against a pool
    # already capped at MAX_SUGGESTIONS; take the first auto_target survivors
    # (auto_target <= MAX_SUGGESTIONS, so this slice is a no-op in practice
    # unless attrition left fewer than auto_target).
    auto_filled = verified[:auto_target]

    status = "ok" if auto_filled else "empty"
    return {"status": status, "candidates": _merge_user_and_auto(user_as_candidates, auto_filled)}
