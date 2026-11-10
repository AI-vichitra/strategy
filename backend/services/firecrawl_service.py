"""
Firecrawl Service
==================
Wraps the Firecrawl REST API (https://api.firecrawl.dev) for optional web-scrape
enrichment of the research pipeline. Only called when a Firecrawl API key is
available (see connector_service.get_api_key + pipeline_service.py's
integration) — never required. Never logs the api_key.
"""

import logging
from typing import List, Optional

import requests

logger = logging.getLogger(__name__)

FIRECRAWL_BASE_URL = "https://api.firecrawl.dev/v2"
SCRAPE_TIMEOUT = 60
MAP_TIMEOUT = 30


def scrape_url(url: str, api_key: str) -> Optional[str]:
    """
    Scrapes a single URL via Firecrawl v2's /scrape endpoint.
    Returns the page content as markdown, or None on any failure.
    """
    if not url or not api_key:
        return None
    try:
        resp = requests.post(
            f"{FIRECRAWL_BASE_URL}/scrape",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"url": url, "formats": ["markdown"], "onlyMainContent": True},
            timeout=SCRAPE_TIMEOUT,
        )
        resp.raise_for_status()
        payload = resp.json() or {}
        content = (payload.get("data") or {}).get("markdown")
        content = (content or "").strip()
        return content or None
    except Exception as e:
        logger.warning(f"[firecrawl] scrape_url failed for {url}: {type(e).__name__}: {e}")
        return None


def crawl_site(url: str, api_key: str, limit: int = 5) -> List[str]:
    """
    Shallow multi-page crawl: maps the site for links via Firecrawl v2's /map
    endpoint, then scrapes up to `limit` of them. Returns the scraped page
    contents (markdown). Never raises — returns [] on any failure.
    """
    if not url or not api_key:
        return []
    try:
        resp = requests.post(
            f"{FIRECRAWL_BASE_URL}/map",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"url": url, "limit": limit},
            timeout=MAP_TIMEOUT,
        )
        resp.raise_for_status()
        raw_links = (resp.json() or {}).get("links") or []
        # v2 links can be plain URL strings or {"url": ..., "title": ...} objects.
        links = [
            (link if isinstance(link, str) else link.get("url"))
            for link in raw_links
        ]
        links = [link for link in links if link]
    except Exception as e:
        logger.warning(f"[firecrawl] crawl_site map failed for {url}: {type(e).__name__}: {e}")
        return []

    pages: List[str] = []
    for link in links[:limit]:
        content = scrape_url(link, api_key)
        if content:
            pages.append(content)
    return pages
