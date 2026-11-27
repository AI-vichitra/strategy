"""
Step 3 Research Service
========================
Standalone, pure-function research execution for the Step 3 "Research
Direction" screen (BRD §3.5.4). Given a brand and a research_direction block
(the same shape ResearchDirection.tsx persists into
Project.questionnaire_answers.research_direction), fans out live web queries
— one per (heading x applicable market level), plus one per custom topic —
and returns a list of docs already shaped the way ai_service._load_json_docs
expects: {title, url, source_type, brand, content, sources, market_level}.

This module does NOT touch the DB, does NOT write kb_json, and does NOT
import ai_service — wiring this into stream_chat/the index/a DB column is a
later pass (B3). It reuses the repo's existing Tavily/Exa primitives (no new
HTTP client): Tavily's own client.search(query=...) is the same arbitrary-
query call run_web_scrape/run_risk_research/run_depth_research already make;
exa_service.search_contents is the fallback when no Tavily key is configured.
Firecrawl is deliberately NOT used here — it is URL-scrape only, not a
free-text query primitive (see tavily_service.py / firecrawl_service.py).

A query that errors or returns nothing still yields a doc — its content
states plainly that data was limited for that heading/market, sources=[] —
so the honesty rule (§3.11) has real grounding instead of silent gaps.
"""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

DEFAULT_MAX_QUERIES = 12
ENV_MAX_QUERIES = "STEP3_MAX_RESEARCH_QUERIES"
DEFAULT_NUM_RESULTS = 4
DEFAULT_CONCURRENCY = 3
MAX_LOCAL_CITIES = 5  # E16

# Headings that force a global-level query regardless of the selected market
# (BRD §3.5.4). "competition" only forces it when its global_benchmarks
# sub-header is actually among the included sub-headers for that heading.
_ALWAYS_GLOBAL_HEADING = "culture_trends"
_COMPETITION_HEADING = "competition"
_COMPETITION_GLOBAL_BENCHMARK_SUBHEADER = "global_benchmarks"

_LEVEL_ORDER = {"national": 0, "global": 1, "local": 2}

# Breadth-first query priority (what the STEP3_MAX_RESEARCH_QUERIES cap keeps
# vs. drops — see build_query_set). Catalog-order-then-levels-then-topics
# used to starve later headings/custom topics entirely at a low cap (every
# level of heading #1 got kept before heading #2 got anything). This layering
# guarantees every ticked heading keeps its PRIMARY level before any heading
# gets a SECONDARY, and so on, with custom topics ranked between secondary
# and tertiary:
#   Layer 0 — every heading's PRIMARY  (level_rank 0: national, if selected — else whichever is first)
#   Layer 1 — every heading's SECONDARY (level_rank 1)
#   Layer 2 — every custom topic
#   Layer 3 — every heading's TERTIARY (level_rank 2)
#   Layer 4 — every heading's QUATERNARY+ (level_rank 3+, e.g. extra compare cities)
_LAYER_PRIMARY = 0
_LAYER_SECONDARY = 1
_LAYER_CUSTOM_TOPIC = 2
_LAYER_TERTIARY = 3
_LAYER_QUATERNARY_PLUS = 4


def _heading_query_layer(level_rank: int) -> int:
    if level_rank == 0:
        return _LAYER_PRIMARY
    if level_rank == 1:
        return _LAYER_SECONDARY
    if level_rank == 2:
        return _LAYER_TERTIARY
    return _LAYER_QUATERNARY_PLUS


# ─────────────────────────────────────────────────────────────────────────────
# Market / level resolution
# ─────────────────────────────────────────────────────────────────────────────
def _selected_levels(market: Dict[str, Any]) -> List[Tuple[str, Optional[str]]]:
    """Returns the (level, detail) pairs actually selected in research_direction.market.
    "local" expands to one entry per city under multi_city_mode="compare" (capped at
    MAX_LOCAL_CITIES, E16), or one combined entry (cities joined) otherwise."""
    levels: List[Tuple[str, Optional[str]]] = []
    if market.get("global"):
        levels.append(("global", None))
    national = market.get("national")
    if national:
        levels.append(("national", national))
    local_cities = [c for c in (market.get("local") or []) if c]
    if local_cities:
        if market.get("multi_city_mode") == "compare":
            for city in local_cities[:MAX_LOCAL_CITIES]:
                levels.append(("local", city))
        else:
            levels.append(("local", ", ".join(local_cities[:MAX_LOCAL_CITIES])))
    return levels


def _resolve_focus(heading: Dict[str, Any], sub_headers_selection: Dict[str, Any]) -> Tuple[List[str], set]:
    """Resolves which of this heading's sub-headers are "in focus" for query
    text — all of them if the heading was never customised (key absent),
    else only the selected ones (possibly none). Returns (focus labels,
    included sub-header ids) — the ids are needed separately to check the
    competition/global_benchmarks forced-global rule."""
    sub_catalog = {
        s["id"]: s.get("label", s["id"])
        for s in (heading.get("sub_headers") or [])
        if isinstance(s, dict) and s.get("id")
    }
    selection = sub_headers_selection.get(heading.get("id"))
    if selection is None:
        return list(sub_catalog.values()), set(sub_catalog.keys())
    included_ids = {sid for sid in selection if sid in sub_catalog}
    return [sub_catalog[sid] for sid in selection if sid in sub_catalog], included_ids


def _heading_levels(
    heading_id: str, included_sub_header_ids: set, selected_levels: List[Tuple[str, Optional[str]]]
) -> List[Tuple[str, Optional[str]]]:
    """Applies the per-heading forcing rules on top of the selected levels,
    then orders national -> global -> local — this per-heading order is what
    build_query_set enumerates to assign each entry its level_rank (0, 1,
    2, ...) for the breadth-first cross-heading priority."""
    levels = list(selected_levels)
    has_global = any(level == "global" for level, _ in levels)
    if heading_id == _ALWAYS_GLOBAL_HEADING and not has_global:
        levels.append(("global", None))
    elif (
        heading_id == _COMPETITION_HEADING
        and _COMPETITION_GLOBAL_BENCHMARK_SUBHEADER in included_sub_header_ids
        and not has_global
    ):
        levels.append(("global", None))
    return sorted(levels, key=lambda lv: _LEVEL_ORDER.get(lv[0], 3))


# ─────────────────────────────────────────────────────────────────────────────
# Query text
# ─────────────────────────────────────────────────────────────────────────────
def _level_label(level: Optional[str], detail: Optional[str]) -> str:
    if level == "global":
        return "Global"
    if level == "national":
        return f"National — {detail}" if detail else "National"
    if level == "local":
        return f"Local — {detail}" if detail else "Local"
    return ""


def _geo_phrase(level: Optional[str], detail: Optional[str]) -> str:
    if level == "global":
        return "global market"
    if level == "national":
        return f"{detail} market" if detail else "national market"
    if level == "local":
        return detail or "local market"
    return ""


def _build_heading_query(brand_name: str, category: str, heading_label: str, focus_labels: List[str], level: str, detail: Optional[str]) -> str:
    focus = "; ".join(focus_labels) if focus_labels else heading_label
    return f"{brand_name} {category} — {heading_label}: {focus} — {_geo_phrase(level, detail)}".strip()


def _build_custom_topic_query(brand_name: str, category: str, topic: str) -> str:
    return f"{brand_name} {category} — {topic}".strip()


# ─────────────────────────────────────────────────────────────────────────────
# Query-set builder (pure, no network — unit-testable on its own)
# ─────────────────────────────────────────────────────────────────────────────
def build_query_set(
    research_direction: Dict[str, Any], brand_name: str, category: str, max_queries: Optional[int] = None
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Builds the full query plan for a research_direction block — WHICH
    queries exist is unchanged from before this priority rework — then sorts
    it by breadth-first priority (see the _LAYER_* constants above) and
    splits it at the cap. Returns (kept, dropped) — both lists of query-plan
    dicts, each now additionally carrying "priority" (layer, group_index,
    level_rank), the exact key sorted on (never raises; a malformed/absent
    research_direction yields ([], []))."""
    if not isinstance(research_direction, dict):
        research_direction = {}

    from backend.services import task_service
    catalog = task_service.get_research_headings()

    ticked = set(research_direction.get("headings") or [])
    sub_headers_selection = research_direction.get("sub_headers")
    if not isinstance(sub_headers_selection, dict):
        sub_headers_selection = {}
    market = research_direction.get("market")
    if not isinstance(market, dict):
        market = {}
    selected_levels = _selected_levels(market)

    plan: List[Dict[str, Any]] = []
    for group_index, heading in enumerate(catalog):
        hid = heading.get("id")
        if not hid or hid not in ticked:
            continue
        label = heading.get("label", hid)
        focus_labels, included_ids = _resolve_focus(heading, sub_headers_selection)
        for level_rank, (level, detail) in enumerate(_heading_levels(hid, included_ids, selected_levels)):
            plan.append({
                "heading_id": hid,
                "heading_label": label,
                "level": level,
                "detail": detail,
                "market_level": level,
                "is_custom_topic": False,
                "query": _build_heading_query(brand_name, category, label, focus_labels, level, detail),
                "priority": (_heading_query_layer(level_rank), group_index, level_rank),
            })

    for topic_index, topic in enumerate(research_direction.get("custom_topics") or []):
        if not isinstance(topic, str) or not topic.strip():
            continue
        clean_topic = topic.strip()
        plan.append({
            "heading_id": None,
            "heading_label": clean_topic,
            "level": None,
            "detail": None,
            "market_level": None,
            "is_custom_topic": True,
            "query": _build_custom_topic_query(brand_name, category, clean_topic),
            "priority": (_LAYER_CUSTOM_TOPIC, topic_index, 0),
        })

    # Stable sort: within identical priority tuples (can't happen across
    # different headings/topics, only in principle for duplicate entries),
    # original construction order is preserved.
    plan.sort(key=lambda q: q["priority"])

    if max_queries is None:
        max_queries = int(os.environ.get(ENV_MAX_QUERIES, str(DEFAULT_MAX_QUERIES)))
    cap = max(0, max_queries)
    return plan[:cap], plan[cap:]


# ─────────────────────────────────────────────────────────────────────────────
# Query execution (sync tool calls — run via asyncio.to_thread, same pattern
# onboarding's pipeline_service.py uses for every tavily_service.* call)
# ─────────────────────────────────────────────────────────────────────────────
def _search_tavily(query_text: str, num_results: int) -> Tuple[str, List[Dict[str, str]]]:
    """The SAME primitive run_web_scrape/run_risk_research/run_depth_research
    already call with their own free-text queries. Raises RuntimeError
    (propagated from tavily_service._get_client) when TAVILY_API_KEY is
    unset — caller falls back to Exa on that specific error."""
    from backend.services.tavily_service import _get_client
    client = _get_client()
    resp = client.search(query=query_text, search_depth="basic", max_results=num_results, include_answer=True)
    answer = (resp.get("answer") or "").strip()
    results = [
        {"title": r.get("title", "") or "", "url": r.get("url", "") or "", "text": (r.get("content", "") or "").strip()}
        for r in (resp.get("results") or [])[:num_results]
    ]
    return answer, results


def _search_exa(query_text: str, num_results: int) -> Tuple[str, List[Dict[str, str]]]:
    """Fallback query primitive. Resolves EXA_API_KEY from the environment
    directly (this module takes no db/user_id, so it cannot call
    connector_service.get_api_key — same env var NAME as that helper's own
    env_fallback, just read without the DB-backed per-user override)."""
    api_key = os.environ.get("EXA_API_KEY", "")
    if not api_key:
        return "", []
    from backend.services.exa_service import search_contents
    raw = search_contents(query_text, api_key, num_results=num_results)
    results = [
        {"title": r.get("title", "") or "", "url": r.get("url", "") or "", "text": (r.get("text", "") or "").strip()}
        for r in raw
    ]
    return "", results


def _run_query_sync(query_text: str, num_results: int) -> Tuple[str, List[Dict[str, str]]]:
    """Never raises. Tries Tavily first (preferred per DIAGNOSE), falls back
    to Exa on any Tavily failure (no key, rate limit, network, etc.), and
    returns ("", []) if both are unavailable/fail — the caller turns that
    into a "data was limited" doc rather than dropping anything silently."""
    try:
        return _search_tavily(query_text, num_results)
    except RuntimeError:
        pass  # no Tavily key configured — fall through to Exa
    except Exception as e:
        logger.warning(f"[step3-research] Tavily query failed for '{query_text}': {type(e).__name__}: {e}")
    try:
        return _search_exa(query_text, num_results)
    except Exception as e:
        logger.warning(f"[step3-research] Exa query failed for '{query_text}': {type(e).__name__}: {e}")
    return "", []


# ─────────────────────────────────────────────────────────────────────────────
# Doc assembly — mirrors tavily_service.run_risk_research's doc shape
# ─────────────────────────────────────────────────────────────────────────────
def _assemble_doc(
    brand_name: str, brand_url: str, qplan: Dict[str, Any], answer: str, results: List[Dict[str, str]]
) -> Dict[str, Any]:
    if qplan.get("is_custom_topic"):
        context_label = f"Custom topic: {qplan['heading_label']}"
    else:
        context_label = f"{qplan['heading_label']} — {_level_label(qplan['level'], qplan['detail'])}"

    parts = []
    if answer:
        parts.append(answer)
    for r in results:
        text = (r.get("text") or "").strip()
        if text:
            parts.append(text)

    if parts:
        content = f"[{context_label}]\n" + "\n\n".join(parts)
    else:
        content = (
            f"[{context_label}] Data was limited for this heading/market — no usable "
            "research results were returned."
        )

    sources = [{"title": r.get("title", ""), "url": r.get("url", "")} for r in results if r.get("url")]

    return {
        "title": f"{brand_name} — {context_label} — Step 3 Research",
        "url": brand_url or "",
        "source_type": "step3_research",
        "brand": brand_name,
        "content": content,
        "sources": sources,
        "market_level": qplan.get("market_level"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────
async def run_step3_research(
    brand_name: str,
    brand_url: str,
    category: str,
    research_direction: Dict[str, Any],
    *,
    max_queries: Optional[int] = None,
    num_results: int = DEFAULT_NUM_RESULTS,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> List[Dict[str, Any]]:
    """Fans out one live query per (ticked heading x applicable market level)
    plus one per custom topic (hard-capped — see build_query_set), executes
    them with bounded concurrency, and returns a doc per query in the same
    shape ai_service._load_json_docs already indexes. Pure: no DB, no
    kb_json, no ai_service import. Never raises — a failed/empty query still
    yields a "data was limited" doc instead of being dropped."""
    kept, dropped = build_query_set(research_direction, brand_name, category, max_queries=max_queries)
    if dropped:
        logger.info(
            f"[step3-research] query cap applied for '{brand_name}': kept {len(kept)}, "
            f"dropped {len(dropped)} — dropped queries: " + "; ".join(q["query"] for q in dropped)
        )

    sem = asyncio.Semaphore(max(1, concurrency))

    async def _run_one(qplan: Dict[str, Any]) -> Dict[str, Any]:
        async with sem:
            try:
                answer, results = await asyncio.to_thread(_run_query_sync, qplan["query"], num_results)
            except Exception as e:
                # Defense-in-depth: _run_query_sync already never raises, but a
                # batch must survive even a to_thread/scheduling-level failure.
                logger.warning(f"[step3-research] query raised for '{qplan['query']}': {type(e).__name__}: {e}")
                answer, results = "", []
            return _assemble_doc(brand_name, brand_url, qplan, answer, results)

    return list(await asyncio.gather(*[_run_one(q) for q in kept]))
