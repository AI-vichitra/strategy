"""
Exa Service
===========
Wraps the Exa semantic search API (https://api.exa.ai) for optional enrichment
of the research pipeline. Only called when an Exa API key is available (see
connector_service.get_api_key + pipeline_service.py's integration) — never
required. Never logs the api_key. Mirrors firecrawl_service.py's shape.
"""

import logging
from typing import List, Dict

import requests

logger = logging.getLogger(__name__)

EXA_SEARCH_URL = "https://api.exa.ai/search"
REQUEST_TIMEOUT = 30


def search_contents(query: str, api_key: str, num_results: int = 5) -> List[Dict]:
    """
    Runs a semantic search via Exa's /search endpoint with page text included.
    Returns a list of {title, url, text} dicts, or [] on any failure.
    """
    if not query or not api_key:
        return []
    try:
        resp = requests.post(
            EXA_SEARCH_URL,
            headers={
                "x-api-key": api_key,
                "Content-Type": "application/json",
            },
            json={"query": query, "numResults": num_results, "contents": {"text": True}},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        results = (resp.json() or {}).get("results") or []
        out: List[Dict] = []
        for r in results:
            text = (r.get("text") or "").strip()
            if not text:
                continue
            out.append({
                "title": r.get("title") or "",
                "url": r.get("url") or "",
                "text": text,
            })
        return out
    except Exception as e:
        logger.warning(f"[exa] search_contents failed for query '{query}': {type(e).__name__}: {e}")
        return []
