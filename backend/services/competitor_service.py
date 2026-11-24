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


def _simplify(s: str) -> str:
    """Lower-cased alnum-only blob, for substring-style name/domain
    comparisons that shouldn't care about spacing, hyphens, or case."""
    return re.sub(r"[^a-z0-9]", "", s.lower())


# ── Pass 2 name→domain matching ──────────────────────────────────────────────
# Directory/aggregator/registry/news/social domains that routinely surface in
# a "{name} official website" search but are never a company's own site.
# Pass 2's token match (below) already rejects most of these on its own —
# the word "sobha" doesn't appear in "leadiq.com" — but a few generic hosts
# (investor-data sites, UK's company registry, Tavily's own knowledge cards)
# are short/generic enough, or built from the query text itself, that they
# can accidentally pass a token check and need excluding outright.
_EXCLUDED_URL_DOMAINS = (
    "linkedin.com", "facebook.com", "twitter.com", "instagram.com", "youtube.com",
    "wikipedia.org", "crunchbase.com", "tracxn.com", "zaubacorp.com", "tofler.in",
    "leadiq.com", "cbinsights.com", "investing.com", "gov.uk", "tavily.com",
    "indiatimes.com", "salezshark.com", "owler.com", "rocketreach.co",
)

# Generic legal-entity words a company's own domain routinely omits (e.g.
# "Sobha Limited" -> sobha.com, "Prestige Group" -> prestigeconstructions.com)
# — stripped before the domain-token match so these don't force a false
# rejection of the real site. Deliberately excludes words that ARE part of a
# brand's actual identity even though they look generic in isolation (e.g.
# "Lifespaces", "Properties", "Realty", "Homes") — those routinely DO show up
# in the real domain and are exactly the qualifier that must be matched to
# reject a same-family parent domain like mahindra.com for "Mahindra
# Lifespaces".
_GENERIC_SUFFIX_TOKENS = {
    "limited", "ltd", "llp", "llc", "inc", "incorporated", "corp",
    "corporation", "co", "company", "pvt", "private", "plc", "group",
}


def _name_tokens(name: str) -> List[str]:
    """Lower-cased word tokens from a company name with generic legal-entity
    suffixes dropped. Every remaining token must appear in a candidate
    domain for it to be accepted — see _domain_matches_tokens below."""
    raw = re.findall(r"[a-z0-9]+", name.lower())
    tokens = [t for t in raw if t not in _GENERIC_SUFFIX_TOKENS]
    return tokens or raw  # never empty-out a name that's ONLY suffix words


def _domain_root(domain: str) -> str:
    """The first label of a domain (e.g. 'sobha' from 'sobha.com', or
    'mahindralifespaces' from 'mahindralifespaces.com'), simplified."""
    return _simplify(domain.split(".")[0])


def _domain_matches_tokens(domain_root: str, tokens: List[str]) -> bool:
    """ALL of the name's significant tokens must appear in the domain — not
    merely one of them. This is what rejects mahindra.com for 'Mahindra
    Lifespaces' (missing the 'lifespaces' qualifier) while still accepting
    dlf.in for 'DLF' and sobha.com for 'Sobha Limited'."""
    return bool(tokens) and all(t in domain_root for t in tokens)


def _specificity_gap(domain_root: str, tokens: List[str]) -> int:
    """How many extra characters domain_root has beyond the matched name
    tokens — 0 for an exact match. Used to prefer the more specific/exact
    domain when several candidates all pass the token match (e.g. picking
    'm3mindia.com' over 'm3mpropertyindia.com' for 'M3M India')."""
    return max(0, len(domain_root) - sum(len(t) for t in tokens))


# A same-named company can genuinely exist in a different country (Sobha
# Realty in Dubai vs. Sobha Limited in India; a US "Prestige Real Estate
# Group" vs. India's Prestige Group) — the domain/token match alone can't
# tell those apart, since both legitimately contain the shared brand word.
# This is a coarse, explicit-conflict-only check: it only rejects a
# candidate when its OWN text clearly names a market different from the
# brand's, and never rejects for silence (no markers found either way).
_MARKET_MARKERS = {
    "india": ("india", "bengaluru", "bangalore", "mumbai", "delhi ncr", "new delhi",
              "gurugram", "gurgaon", "noida", "pune", "hyderabad", "chennai",
              "kolkata", "haryana", "maharashtra", "karnataka"),
    "uae": ("dubai", "abu dhabi", "u.a.e", "uae", "united arab emirates"),
    "usa": ("united states", "u.s.a", "usa", "colorado", "california", "texas"),
    "uk": ("united kingdom", " uk ", "london"),
    "singapore": ("singapore",),
    "qatar": ("qatar", "doha"),
    "saudi arabia": ("saudi arabia", "riyadh", "jeddah"),
}


def _infer_markets(text: str) -> set:
    t = f" {text.lower()} "
    return {market for market, markers in _MARKET_MARKERS.items() if any(m in t for m in markers)}


def _geography_conflicts(brand_geography: Optional[str], candidate_text: str) -> bool:
    """True only when the candidate's own text names a known market that is
    explicitly DIFFERENT from the brand's own known market — e.g. rejecting
    a Dubai-market page for an India-market brand's competitor list. Silent
    (no detectable market on either side) never counts as a conflict."""
    if not brand_geography or brand_geography == "unknown":
        return False
    brand_markets = _infer_markets(brand_geography)
    if not brand_markets:
        return False
    candidate_markets = _infer_markets(candidate_text)
    if not candidate_markets:
        return False
    return not (brand_markets & candidate_markets)


# Catches a page that explicitly disclaims being the company's own site
# (e.g. a lookalike/decoy domain: "this is an informational and news
# website, not Godrej Properties' official site") — the domain-token match
# alone can't tell a decoy like this apart from the real thing when it also
# contains every one of the brand's name tokens.
_SELF_DISCLAIMER_RE = re.compile(r"not\b[^.]{0,80}official\s+sites?\b", re.IGNORECASE)

# Other search results (news articles, aggregator "knowledge card" pages)
# routinely restate a company's real domain in their own text even when
# their OWN url is excluded above — e.g. "Website: www.godrejproperties.com"
# on a tavily.com knowledge card. Extracting these recovers the real domain
# in cases where it never appears as a direct, unexcluded search hit at all.
_WEBSITE_MENTION_DOMAIN_RE = re.compile(
    r"(?:official\s+websites?|official\s+sites?|websites?)\s*[:\-|]?\s*(?:is\s+)?"
    r"(?:https?://)?(?:www\.)?([a-z0-9][a-z0-9\-]*\.[a-z]{2,}(?:\.[a-z]{2,})?)",
    re.IGNORECASE,
)


# ── Bare-name identity confirmation (page title / og:site_name) ──────────────
# A BARE name — one significant token after dropping legal suffixes, e.g.
# "Prestige" — is dangerous in Pass 2: the domain-token check only requires the
# token to be a SUBSTRING of the domain root, so "prestige" accepts
# prestigemgt.com (Prestige Management, a US property-management firm) just as
# readily as the real developer's site. For these, the domain match alone is
# not enough; the PAGE'S OWN identity must confirm it is that same company.
#
# Structural/legal + geographic descriptor tokens a real company's own site
# identity routinely carries without changing WHICH company it is (e.g. "Lodha
# Group", "M3M India", "Godrej Properties", "SOBHA Limited"). A token NOT in
# here (e.g. "Management" in "Prestige Management") marks a DIFFERENT company
# that merely shares the brand word — used only by _cache_entry_clearly_wrong.
_BENIGN_IDENTITY_QUALIFIERS = {
    "properties", "property", "realty", "estate", "estates", "developers",
    "developer", "construction", "constructions", "projects", "project",
    "builders", "builder", "homes", "infra", "infrastructure", "land",
    "india", "indian", "global", "international",
}


# One-request-per-URL page cache, shared by the identity check AND the
# geography check so a candidate's site is fetched at most ONCE per process.
# Keyed by URL -> {"identity": <str>, "text": <lowercased body text>}.
_PAGE_FETCH_CACHE: Dict[str, Dict[str, str]] = {}


def _fetch_page_fields(url: str) -> Dict[str, str]:
    """Fetch `url` ONCE (SSRF-guarded, via social_links_service's shared
    fetch/parse) and return {"identity", "text"}:
      - identity: og:site_name if present, else the first <title> segment
        (split on | – — - :). "" when the page yields no identity.
      - text:     cleaned, lowercased visible body text (for the geography
        check), "" on a failed/blocked fetch.
    Memoized per URL for this process, so the identity check and the geography
    check never issue two requests for the same candidate."""
    if url in _PAGE_FETCH_CACHE:
        return _PAGE_FETCH_CACHE[url]
    out = {"identity": "", "text": ""}
    from backend.services import social_links_service
    try:
        soup = social_links_service._fetch_and_parse(url)
    except Exception:
        soup = None
    if soup is not None:
        # Identity MUST be read before _text_from_soup, which decomposes
        # <head> (where og:site_name/<title> live) while extracting body text.
        tag = soup.find("meta", property="og:site_name")
        if tag and (tag.get("content") or "").strip():
            out["identity"] = tag["content"].strip()
        elif soup.title and (soup.title.string or "").strip():
            out["identity"] = re.split(r"\s*[|–—\-:]\s*", soup.title.string.strip(), maxsplit=1)[0].strip()
        try:
            out["text"] = social_links_service._text_from_soup(soup).lower()
        except Exception:
            out["text"] = ""
    _PAGE_FETCH_CACHE[url] = out
    return out


def _page_identity(url: str) -> str:
    """The page's own identity string (og:site_name or first <title> segment),
    "" on any failure. Thin accessor over the cached _fetch_page_fields."""
    return _fetch_page_fields(url)["identity"]


def _identity_status(identity: str, tokens: List[str]) -> str:
    """Classify a resolved page's own identity against the competitor NAME, for
    BOTH bare and multi-token names. Returns:
      - "none"      : the page yielded no identity (unreachable / no og / no
                      title). NOT treated as confirmation — recorded as-is so
                      an empty identity never passes silently.
      - "mismatch"  : the identity names a DIFFERENT company — it SHARES the
                      brand's token(s) but ALSO carries a distinctive token
                      (after removing benign structural/geo qualifiers) the
                      name does not, e.g. "Prestige Management" for "Prestige".
                      Caller rejects the URL.
      - "confirmed" : the identity shares the name's distinctive token(s) and
                      introduces no conflicting one (extra tokens, if any, are
                      benign qualifiers like Group/Properties/India).
    A title that shares NOTHING with the name (e.g. a tagline like "Top Builder
    in Gurugram" for "Signature Global") is "none", NOT "mismatch": it is no
    evidence of a different company, so it must not drop a domain-matched
    multi-token candidate — it is simply an unconfirmed identity.
    """
    if not identity:
        return "none"
    id_tokens = set(_name_tokens(identity))
    name_set = set(tokens)
    shared = id_tokens & name_set
    if not shared:
        return "none"
    extra = id_tokens - name_set - _BENIGN_IDENTITY_QUALIFIERS
    return "mismatch" if extra else "confirmed"


def _geo_evidence(url: str, needles: List[str]) -> List[str]:
    """Markers of the user's own geography (cities, their metros, region) found
    in the candidate's OWN site text — reusing the cached page fetch. An empty
    list means no on-site evidence it operates in the user's market; it is NOT
    proof it doesn't (a national developer may still compete locally), so the
    caller DEMOTES on empty evidence, never drops."""
    text = _fetch_page_fields(url).get("text", "")
    if not text:
        return []
    found = []
    for n in needles:
        nl = n.strip().lower()
        if nl and nl in text and nl not in found:
            found.append(nl)
    return found


def _cache_entry_clearly_wrong(identity: str, tokens: List[str]) -> bool:
    """True when a cached bare-name URL's page identity names a DIFFERENT
    company — it carries a distinguishing token that is neither the brand nor a
    benign structural/geographic qualifier (e.g. "Management"). Deliberately
    more lenient than the acceptance gate: a genuinely-correct geo-qualified
    entry (M3M -> "M3M India") is KEPT, while a wrong one (Prestige ->
    "Prestige Management Inc.") is pruned. An empty/unreachable identity is NOT
    clearly wrong — a transient fetch failure must never evict a good entry."""
    if not identity:
        return False
    residual = set(_name_tokens(identity)) - _BENIGN_IDENTITY_QUALIFIERS
    return residual != set(tokens)


# ── Persisted name→URL cache ─────────────────────────────────────────────────
# Keeps repeat competitors (DLF, Godrej, Sobha, ...) resolving to the SAME
# domain run after run, instead of depending on whatever that run's Tavily
# search happened to rank highest. Keyed on the simplified name ALONE — a
# known simplification (two genuinely different companies sharing a name
# across unrelated industries would collide) accepted for this module's
# scope. Only successful resolutions are cached; a blank ("no URL found") is
# never cached, so a later run with better search results can still find
# one instead of being locked into "no site" forever.
_URL_CACHE_PATH = os.path.join(_PROJECT_ROOT, "backend", "data", "competitor_url_cache.json")


def _load_url_cache() -> Dict[str, Dict[str, str]]:
    """Best-effort read — a missing/corrupt cache file is just an empty cache, never raised."""
    try:
        with open(_URL_CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_url_cache(cache: Dict[str, Dict[str, str]]) -> None:
    """Best-effort write — a failure here (e.g. read-only filesystem) never breaks resolution."""
    try:
        os.makedirs(os.path.dirname(_URL_CACHE_PATH), exist_ok=True)
        with open(_URL_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, sort_keys=True)
    except Exception as e:
        logger.warning(f"[CompetitorService] Failed to persist URL cache: {e}")


def revalidate_url_cache() -> Dict[str, Any]:
    """Prune persisted cache entries whose stored bare-name URL now fails the
    stricter identity check — i.e. its page identity names a DIFFERENT company
    (see _cache_entry_clearly_wrong). Blanks are never cached, so a pruned name
    simply re-resolves fresh (with the new acceptance gate) on its next run,
    which is how a wrong entry like "Prestige" -> prestigemgt.com gets replaced
    by the right site. Correct geo-qualified entries (e.g. M3M -> "M3M India")
    are kept. Returns {"removed": {...}, "kept": [...]}. Safe to run repeatedly."""
    cache = _load_url_cache()
    removed: Dict[str, Dict[str, str]] = {}
    kept: List[str] = []
    for key in list(cache.keys()):
        entry = cache[key]
        name = entry.get("name", "")
        url = entry.get("url", "")
        tokens = _name_tokens(name)
        if url and len(tokens) <= 1:
            identity = _page_identity(url)
            if _cache_entry_clearly_wrong(identity, tokens):
                removed[key] = {"url": url, "identity": identity or "<unreachable>"}
                del cache[key]
                continue
        kept.append(key)
    if removed:
        _save_url_cache(cache)
    logger.info(f"[CompetitorService] revalidate_url_cache removed={list(removed)} kept={kept}")
    return {"removed": removed, "kept": kept}


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
    segment: Optional[str] = None,
    geography: Optional[str] = None,
    target_market: Optional[Dict[str, Any]] = None,
) -> Optional[List[Dict[str, Any]]]:
    """
    Two-pass resolution of Tavily's raw structured (article) results into
    clean {name, website_url, source_url, summary} competitor entries.

    Pass 1 — LLM extracts competitor brand NAMES ONLY from the article
    content (title/snippet). Trustworthy because it never fabricates a URL.
    When segment/geography (inferred from the brand's own fetched content —
    see tavily_comp._research_brand_scope) are known, Pass 1 is told to
    PREFER matching candidates as a ranking signal only, never a hard filter
    — a clearly major rival is never excluded just for being more national.
    Pass 2 — a dedicated Tavily lookup per extracted name
    ("{name} official website {product_focus}") finds that company's own
    domain: a candidate must contain EVERY significant word of the name
    (not just one), must not itself disclaim being the official site, and
    must not name a market that conflicts with the brand's own known
    geography — see _resolve_pass2_url's own docstring below for the full
    cache -> search -> token/disclaimer/geography -> specificity pipeline.
    A name Pass 2 can't resolve still survives with website_url="" (never
    None — see
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

    # The user's own target_market cities are the AUTHORITATIVE geography and
    # take precedence over the LLM-inferred `geography` — the inference is only
    # the fallback when the user supplied no cities. This is what makes a
    # developer active in the user's cities outrank a national-listicle name.
    user_cities = (
        [c.strip() for c in (target_market.get("cities") or []) if c and c.strip()]
        if target_market else []
    )
    user_region = (target_market.get("region") or "").strip() if target_market else ""

    # Geography needles for the per-candidate evidence check below: the user's
    # cities, each metro-expanded (so "Gurugram" also matches a page that says
    # "Delhi NCR"), plus the region. A candidate whose own site names any of
    # these demonstrably operates in the user's market; one that names none is
    # demoted (not dropped). Empty when no target_market was supplied.
    geo_needles: List[str] = []
    if target_market:
        from web_scrapper.tavily_comp import _expand_to_metro
        for c in user_cities:
            geo_needles.append(c)
            metro = _expand_to_metro(c)
            if metro and metro.lower() != c.lower():
                geo_needles.append(metro)
        if user_region and user_region.lower() not in ("global", "local"):
            geo_needles.append(user_region)
        _seen_needle = set()
        geo_needles = [n for n in geo_needles if not (n.lower() in _seen_needle or _seen_needle.add(n.lower()))]

    scope_clause = ""
    if segment and segment != "unknown":
        scope_clause += f"\n- PREFER competitors that also operate in the '{segment}' segment/tier of {focus}, when the search results let you tell segment apart. Do NOT drop a clearly major, well-known rival just because it's broader/more national than that segment — this is a ranking preference, not a hard filter."
    if user_cities:
        cities_str = ", ".join(user_cities)
        region_note = f" (region: {user_region})" if user_region and user_region.lower() not in ("global", "local") else ""
        scope_clause += (
            f"\n- The brand's TARGET MARKET is {cities_str}{region_note}. PREFER competitors that "
            f"actively operate in {cities_str}: a developer present in these cities must RANK ABOVE a "
            f"nationally-broad or differently-located name. This is the authoritative geography and takes "
            f"precedence over any broader inferred region. Still don't drop a clearly major rival outright — rank, don't hard-filter."
        )
    elif geography and geography != "unknown":
        scope_clause += f"\n- PREFER competitors primarily operating in '{geography}', when the search results let you tell geography apart. Do NOT drop a clearly major, well-known rival just because it operates more broadly than that geography — this is a ranking preference, not a hard filter."

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
        f"- This brand operates in: {focus}. Only include competitors in the same or directly adjacent product space."
        f"{scope_clause}\n"
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
        """
        Resolves one competitor NAME to its own official domain, never a
        same-family parent/sister domain or an unrelated same-named company:

          1. Cache check — a previously-resolved name returns the SAME url
             every time, independent of this run's search results.
          2. A dedicated Tavily lookup ("{name} official website {focus}").
          3. Every result's own url, PLUS any domain mentioned in a result's
             own text ("Website: www.X.com" — recovers the real domain from
             aggregator "knowledge card" pages whose own url is excluded),
             is a CANDIDATE only if:
               a. its domain contains every one of the name's significant
                  tokens (generic legal-entity suffixes dropped) — this is
                  what rejects mahindra.com for "Mahindra Lifespaces": the
                  "lifespaces" qualifier is missing from that domain;
               b. its own text doesn't explicitly disclaim being the
                  official site (catches lookalike/decoy domains);
               c. its own text doesn't name a market that conflicts with
                  the brand's own known geography (catches a same-named
                  sister company in a different country, e.g. Sobha Realty
                  in Dubai vs. Sobha Limited in India).
          4. Among surviving candidates, the MOST SPECIFIC domain wins (the
             smallest gap between the domain and the matched name tokens),
             so an exact match like m3mindia.com is preferred over a looser
             one like m3mpropertyindia.com.
          5. No survivor -> "" (blank). Never a near-miss domain just
             because it was the only or the highest-ranked result.
        """
        cache = _load_url_cache()
        cache_key = _simplify(name)
        if cache_key in cache:
            cached_url = cache[cache_key].get("url", "")
            print(f"[COMP-RESOLVE] Pass 2 — '{name}' → {cached_url or 'no URL found'} (cached)")
            return cached_url

        if pass2_client is None:
            return ""
        try:
            resp = pass2_client.search(
                query=f"{name} official website {focus}",
                search_depth="basic",
                max_results=5,
            )
        except Exception as e:
            logger.warning(f"[CompetitorService] Pass 2 Tavily lookup failed for '{name}': {e}")
            return ""

        tokens = _name_tokens(name)
        results = resp.get("results", []) or []

        # domain -> {"url", "domain_root", "rank"} — first-seen (direct
        # search hit) wins over a same-domain mention extracted later.
        survivors: Dict[str, Dict[str, Any]] = {}

        def _consider(domain: str, url: str, text: str, rank: int) -> None:
            if not domain or domain in survivors:
                return
            domain_root = _domain_root(domain)
            if not _domain_matches_tokens(domain_root, tokens):
                return
            if _SELF_DISCLAIMER_RE.search(text):
                return
            if _geography_conflicts(geography, text):
                return
            # Page-identity confirmation — for BOTH bare and multi-token names.
            # The page is fetched (once, cached) on its normalized root only for
            # candidates that already passed everything above.
            #   bare (1 significant token): the domain-token match is a weak
            #     substring test (prestige ⊂ prestigemgt), so require a positive
            #     "confirmed" — an empty or mismatching identity is rejected.
            #   multi-token: the all-tokens domain match is already strong, so
            #     reject only a clear different-company "mismatch"; an empty
            #     identity does NOT drop the candidate (recorded as "none" so it
            #     never passes silently — see the candidate loop below).
            fetch_url = _normalize_website_url(url)
            identity = _page_identity(fetch_url)
            status = _identity_status(identity, tokens)
            if len(tokens) <= 1:
                if status != "confirmed":
                    return
            elif status == "mismatch":
                return
            survivors[domain] = {
                "url": url, "domain_root": domain_root, "rank": rank,
                "identity": identity, "identity_status": status,
            }

        for rank, r in enumerate(results):
            url = r.get("url", "")
            text = f"{r.get('title', '')} {r.get('content', '')}"
            if url:
                domain = urlparse(url).netloc.lower().replace("www.", "")
                if not any(d in domain for d in _EXCLUDED_URL_DOMAINS):
                    _consider(domain, url, text, rank)
            m = _WEBSITE_MENTION_DOMAIN_RE.search(text)
            if m:
                mentioned_domain = m.group(1).lower()
                _consider(mentioned_domain, f"https://{mentioned_domain}", text, rank)

        if not survivors:
            return ""

        best_domain = min(
            survivors,
            key=lambda d: (_specificity_gap(survivors[d]["domain_root"], tokens), survivors[d]["rank"]),
        )
        resolved_url = _normalize_website_url(survivors[best_domain]["url"])
        cache[cache_key] = {"name": name, "url": resolved_url}
        _save_url_cache(cache)
        return resolved_url

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
        # Identity status + geography evidence for the RESOLVED url — one fetch
        # per candidate, shared with the identity check above via the page
        # cache. An empty identity is reported as "none" (never silently
        # treated as confirmation); geo_evidence lists the user-market markers
        # found on the candidate's own site (empty = demote, not drop).
        identity, identity_status, geo_evidence = "", "no_url", []
        if url:
            fields = _fetch_page_fields(url)
            identity = fields["identity"]
            identity_status = _identity_status(identity, _name_tokens(name))
            geo_evidence = _geo_evidence(url, geo_needles) if geo_needles else []
        print(
            f"[COMP-RESOLVE] Pass 2 — '{name}' → {url or 'no URL found'} "
            f"(identity={identity or 'NONE'!r} status={identity_status} geo_evidence={geo_evidence})"
        )
        candidates.append({
            "name": name,
            "website_url": url,  # "" (never None) when unresolved — see docstring
            "source_url": _find_source_article_url(name),
            "summary": "",
            "identity": identity,
            "identity_status": identity_status,
            "geo_evidence": geo_evidence,
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

    # ── Geography-aware ranking ──────────────────────────────────────────────
    # When the user named a target market, a candidate with on-site evidence it
    # operates there ranks ABOVE one without — a STABLE partition, so within
    # each group the LLM's original competitive ordering is preserved, and a
    # national developer with no local evidence is demoted, never dropped.
    if geo_needles:
        candidates.sort(key=lambda c: 0 if c.get("geo_evidence") else 1)

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
      - RATE LIMIT (429): never dropped and never treated as "not verified".
        Firecrawl backs off and retries; if still throttled, the candidate is
        KEPT (verified=False, verification="rate_limited") and an ERROR is
        logged — losing a live competitor to throttling is an operational
        failure, not a verification result.
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

        try:
            content, status = firecrawl_service.scrape_url_with_status(website_url, firecrawl_key)
        except Exception as e:
            logger.warning(f"[CompetitorService] Firecrawl verification failed for {website_url}: {e}")
            content, status = None, "error"

        if status == "ok":
            verified.append({**item, "verified": True})
        elif status == "rate_limited":
            # A rate limit must NEVER look like "not verified" — keep the
            # candidate and surface the cause loudly instead of silently
            # dropping a possibly-live competitor.
            logger.error(
                f"[COMP-VERIFY] '{item.get('name', '')}' ({website_url}) could NOT be verified — "
                f"Firecrawl rate-limited (429) after retries. Keeping candidate as unverified "
                f"(verification=rate_limited), NOT dropping it."
            )
            verified.append({**item, "verified": False, "verification": "rate_limited"})
        # else ("empty"/"error"): drop — a genuinely dead/empty/erroring URL is
        # exactly the untrustworthy result this check exists to catch.

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
    target_market: Optional[Dict[str, Any]] = None,
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
            brand_name, website_url, category, industry=industry, region=region,
            target_market=target_market,
        )
    except CompetitorDiscoveryFailure:
        raise  # already the right type/message (e.g. "All Tavily search queries failed") — don't rewrap
    except Exception as e:
        raise CompetitorDiscoveryFailure(f"Tavily structured search raised: {e}") from e

    if not isinstance(raw, dict) or "results" not in raw:
        raise CompetitorDiscoveryFailure("Tavily structured search returned a malformed shape")

    raw_results = raw["results"]
    product_focus = raw.get("product_focus") or category
    segment = raw.get("segment")
    geography = raw.get("geography")
    print(
        f"[COMP-RESOLVE] Received {len(raw_results)} candidates from search, "
        f"product_focus='{product_focus}', segment='{segment}', geography='{geography}'"
    )

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
        segment=segment,
        geography=geography,
        target_market=target_market,
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
