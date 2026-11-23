"""
Brand Context Research Service
===============================
Auto-researches a brand's context from trusted web sources (Tavily) and
summarizes it via the existing LLM provider resolver, for the "Research
Brand" auto-fill button on the brand-setup form. Non-blocking: any failure
(missing keys, Tavily/LLM errors, unparseable output) degrades to an empty
string/list rather than raising, so the caller can always fall back to
manual entry.
"""

import logging
import os
from typing import List, Tuple

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

_MAX_RESULTS_PER_QUERY = 5

_SYSTEM_PROMPT = (
    "You are a brand research analyst. Using ONLY the provided search results, "
    "write a concise brand context summary (150-250 words) covering: what the "
    "company does, key products/services, target audience, market positioning, "
    "and any notable facts. If information is insufficient, state what could be "
    "verified. Do not fabricate — only use facts from the provided sources. Cite "
    "source names inline."
)


def _get_tavily_client():
    """Mirrors web_scrapper/tavily_comp.py's client-construction pattern."""
    from tavily import TavilyClient

    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(os.path.dirname(script_dir))
    load_dotenv(os.path.join(base_dir, "backend", ".env"))

    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return None
    return TavilyClient(api_key=api_key)


def _research_brand_context_full(
    brand_name: str, website_url: str, category: str
) -> Tuple[str, List[str]]:
    """Does the actual Tavily search + LLM summarization, returning both the
    summary and the distinct source URLs it was grounded in. Returns ("", [])
    on any failure — Tavily unavailable, every query failing, no LLM key, or
    the completion call raising. Never raises."""
    try:
        client = _get_tavily_client()
        if client is None:
            return "", []

        queries = [
            f"{brand_name} {category} company overview",
            f"{brand_name} official site OR crunchbase OR linkedin",
        ]

        # Reuse the report-generation source denylist (the single source of
        # truth in ai_service — not a second copy): data-scraper/profile
        # aggregators like leadiq.com, rocketreach.co, growjo.com are banned
        # from report citations, so they must not shape the brand's brief or
        # context either. If a source isn't trustworthy enough to cite, it
        # isn't trustworthy enough to define the brand.
        from backend.services.ai_service import _is_denied_source

        all_results = []
        seen_urls = set()
        for query in queries:
            try:
                response = client.search(
                    query=query,
                    search_depth="advanced",
                    max_results=_MAX_RESULTS_PER_QUERY,
                )
            except Exception as e:
                logger.warning(f"[BrandContextService] Tavily query failed: {e}")
                continue

            for r in response.get("results", []) or []:
                url = r.get("url", "")
                if not url or url in seen_urls:
                    continue
                if _is_denied_source(url):
                    logger.info(f"[BrandContextService] Dropped denylisted source: {url}")
                    continue
                seen_urls.add(url)
                all_results.append({
                    "title": r.get("title", ""),
                    "url": url,
                    "snippet": r.get("content", ""),
                })

        if not all_results:
            return "", []

        results_block = "\n".join(
            f"{i + 1}. title: {r['title']}\n"
            f"   url: {r['url']}\n"
            f"   snippet: {(r['snippet'] or '')[:500]}"
            for i, r in enumerate(all_results)
        )
        user_prompt = (
            f"Brand: {brand_name}\n"
            f"Website: {website_url}\n"
            f"Category: {category}\n\n"
            f"Search results:\n{results_block}"
        )

        from backend.services.ai_service import _get_llm_provider

        try:
            _get_llm_provider()
        except RuntimeError:
            return "", []

        from backend.services.slide_planner import _default_llm_completion

        try:
            summary = _default_llm_completion(_SYSTEM_PROMPT, user_prompt)
        except Exception as e:
            logger.warning(f"[BrandContextService] LLM completion failed: {e}")
            return "", []

        summary = (summary or "").strip()
        if not summary:
            return "", []

        sources = [r["url"] for r in all_results]
        return summary, sources
    except Exception as e:
        logger.warning(f"[BrandContextService] research_brand_context failed: {e}")
        return "", []


def research_brand_context(brand_name: str, website_url: str, category: str) -> str:
    """Public entry point per spec: returns just the generated summary string,
    or "" on any failure (non-blocking)."""
    summary, _sources = _research_brand_context_full(brand_name, website_url, category)
    return summary
