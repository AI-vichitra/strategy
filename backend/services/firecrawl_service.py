"""
Firecrawl Service
==================
Wraps the Firecrawl REST API (https://api.firecrawl.dev) for optional web-scrape
enrichment of the research pipeline. Only called when a Firecrawl API key is
available (see connector_service.get_api_key + pipeline_service.py's
integration) — never required. Never logs the api_key.
"""

import logging
import time
from typing import List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

FIRECRAWL_BASE_URL = "https://api.firecrawl.dev/v2"
SCRAPE_TIMEOUT = 60
MAP_TIMEOUT = 30

# 429 (rate limit) retry policy. A rate limit is transient and must NOT be
# treated as a dead/missing page — callers that drop on "no content" would
# otherwise silently lose a live site to throttling. Back off and retry; only
# if still throttled after these waits do we report status="rate_limited".
_RATE_LIMIT_BACKOFFS = (1.0, 2.0, 4.0)

# scrape_with_status statuses:
#   "ok"           -> live page, content returned
#   "empty"        -> 200 but no usable content (treat as dead)
#   "rate_limited" -> 429 persisted through every backoff (transient, NOT dead)
#   "error"        -> any other failure (timeout, 4xx/5xx, network, parse)


def scrape_url_with_status(url: str, api_key: str) -> Tuple[Optional[str], str]:
    """Scrapes a single URL via Firecrawl v2's /scrape endpoint, returning
    (content, status). Retries with backoff on HTTP 429 so a transient rate
    limit is reported as status="rate_limited" (distinct from a dead page)
    rather than an empty result. Never raises."""
    if not url or not api_key:
        return None, "error"

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {"url": url, "formats": ["markdown"], "onlyMainContent": True}

    for attempt in range(len(_RATE_LIMIT_BACKOFFS) + 1):
        try:
            resp = requests.post(
                f"{FIRECRAWL_BASE_URL}/scrape", headers=headers, json=body, timeout=SCRAPE_TIMEOUT,
            )
            if resp.status_code == 429:
                if attempt < len(_RATE_LIMIT_BACKOFFS):
                    wait = _RATE_LIMIT_BACKOFFS[attempt]
                    logger.warning(
                        f"[firecrawl] 429 rate limit for {url} — backing off {wait}s "
                        f"(attempt {attempt + 1}/{len(_RATE_LIMIT_BACKOFFS) + 1})"
                    )
                    time.sleep(wait)
                    continue
                logger.error(f"[firecrawl] scrape_url still 429 after {len(_RATE_LIMIT_BACKOFFS)} retries for {url}")
                return None, "rate_limited"
            resp.raise_for_status()
            payload = resp.json() or {}
            content = ((payload.get("data") or {}).get("markdown") or "").strip()
            return (content, "ok") if content else (None, "empty")
        except Exception as e:
            logger.warning(f"[firecrawl] scrape_url failed for {url}: {type(e).__name__}: {e}")
            return None, "error"
    return None, "error"


def scrape_url(url: str, api_key: str) -> Optional[str]:
    """
    Scrapes a single URL via Firecrawl v2's /scrape endpoint.
    Returns the page content as markdown, or None on any failure.
    Thin back-compat wrapper over scrape_url_with_status (now with 429 retry).
    """
    return scrape_url_with_status(url, api_key)[0]


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
