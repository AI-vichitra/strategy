"""
Social Links Service
=====================
Best-effort, server-side extractor that scans a brand's own website for (a)
links to its social profiles (the platforms in schemas.brand.SOCIAL_PLATFORMS)
and (b) the page's own visible text (for the Brand Brief generator).

Both extractors share ONE internal fetch (_fetch_html) + parse (_parse_html)
step, so a caller wanting both for the same URL never issues two requests.
extract_social_links's existing signature and behaviour are unchanged for
its existing caller.

Feeds a later user-verify step for schemas.brand.social_handles, and the
Brand Brief generator. Results may be partial or empty by design — nothing
here ever raises, so a slow, broken, or blocking site can never hold up
onboarding.

Deliberately NOT built on tavily_service's /extract: that endpoint returns
summarized page text (hrefs may be dropped) and costs API quota for something
a direct HTML fetch + href scan does for free.
"""
import ipaddress
import logging
import re
import socket
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup

from backend.schemas.brand import SOCIAL_PLATFORMS

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_TIMEOUT_SECONDS = 10.0
_MAX_RESPONSE_BYTES = 2_000_000  # social links live in the header/footer, always well within this
_MAX_PAGE_TEXT_CHARS = 25_000
# Below this many chars of visible text, a plain GET almost certainly returned
# a JS shell (or was blocked/empty) rather than real brand copy, and it's worth
# paying for a Firecrawl JS-render instead. Calibrated against real homepages
# measured on a plain GET: in.emaar.com ~2600 chars, godrejproperties.com
# ~1900 — both real content, both an order of magnitude above this floor. A
# genuine SPA shell comes back near-empty, so 500 separates the two cleanly
# without triggering a paid fallback for sites that already render server-side.
_MIN_USEFUL_TEXT_CHARS = 500
# Stripped entirely before text extraction: script/style never contain real
# copy; nav/header/footer/form/head are navigation chrome, menus, and input
# widgets rather than brand content — leaving "header" in particular let
# through mostly menu/contact-bar text on real sites tested (Godrej, Emaar,
# DLF), confirmed by inspecting the extracted output before adding it here.
_TEXT_STRIP_TAGS = ("script", "style", "nav", "header", "footer", "form", "noscript", "head")

# platform -> domain(s) that identify a profile link for that platform.
# Keyed off schemas.brand.SOCIAL_PLATFORMS so the two can never drift apart.
_PLATFORM_DOMAINS = {
    "instagram": ("instagram.com",),
    "linkedin": ("linkedin.com",),
    "x": ("x.com", "twitter.com"),
    "youtube": ("youtube.com", "youtu.be"),
    "facebook": ("facebook.com", "fb.com"),
    "tiktok": ("tiktok.com",),
}
assert set(_PLATFORM_DOMAINS) == set(SOCIAL_PLATFORMS), "platform domain map must match SOCIAL_PLATFORMS exactly"

# Substrings that mark a share/intent link rather than a profile link. A share
# button and a footer profile icon point at the same domain, so domain
# matching alone can't tell them apart — this is the false-positive filter.
_SHARE_MARKERS = (
    "sharer", "share.php", "/share?", "/share/", "intent/tweet", "intent/post",
    "sharearticle", "share-offsite", "/dialog/share", "/dialog/feed",
)


def _is_blocked_host(hostname: str) -> bool:
    """True if hostname is localhost or resolves to a private/loopback/
    link-local address. website_url is user input fetched server-side, so
    this must be checked BEFORE any network call (SSRF guard)."""
    if not hostname:
        return True
    host = hostname.lower()
    if host in ("localhost", "0.0.0.0") or host.endswith(".localhost"):
        return True
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
    except ValueError:
        pass
    # Not a literal IP — resolve it and check the resolved address(es) too, so
    # a hostname that merely points at a private IP is blocked the same way.
    try:
        resolved = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False  # unresolvable -> let the fetch fail naturally, not our job to pre-judge
    for family, _socktype, _proto, _canon, sockaddr in resolved:
        addr = sockaddr[0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return True
    return False


def _validate_url(website_url: str) -> Optional[str]:
    """Returns the URL if it's safe to fetch (http/https, not blocked), else None."""
    if not website_url or not website_url.strip():
        return None
    parsed = urlparse(website_url.strip())
    if parsed.scheme not in ("http", "https"):
        return None
    if not parsed.hostname:
        return None
    if _is_blocked_host(parsed.hostname):
        return None
    return parsed.geturl()


def _href_domain(href: str) -> str:
    """Registrable-ish domain from an href, tolerating scheme-relative
    ("//instagram.com/x") and bare ("instagram.com/x") forms."""
    parsed = urlparse(href)
    netloc = parsed.netloc
    if not netloc and not href.startswith(("/", "#", "mailto:", "tel:", "javascript:")) and "." in href.split("/")[0]:
        parsed = urlparse("//" + href)
        netloc = parsed.netloc
    netloc = netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def _is_share_link(href: str) -> bool:
    lowered = href.lower()
    return any(marker in lowered for marker in _SHARE_MARKERS)


def _profile_depth(path: str) -> int:
    """Lower = closer to a profile root; used to prefer a root profile link
    over a deep link (a specific post/article/video)."""
    return len([p for p in path.strip("/").split("/") if p])


def _canonicalize(href: str) -> str:
    """https, query string and fragment stripped, no trailing slash."""
    parsed = urlparse(href if "//" in href else "//" + href)
    path = parsed.path.rstrip("/")
    return urlunparse(("https", parsed.netloc, path, "", "", ""))


def _pick_best(platform: str, candidates: List[str]) -> Optional[str]:
    if not candidates:
        return None
    pool = candidates
    if platform == "linkedin":
        company = [c for c in pool if "/company/" in urlparse(c).path.lower()]
        if company:
            pool = company
        else:
            personal = [c for c in pool if "/in/" in urlparse(c).path.lower()]
            if personal:
                pool = personal
    pool = sorted(pool, key=lambda c: _profile_depth(urlparse(c).path))
    return pool[0]


def _fetch_html(website_url: str) -> Optional[bytes]:
    """Validates + fetches website_url ONCE; returns raw HTML bytes, or None
    on any failure (rejected URL, timeout, non-200, HTTP error). The single
    network call shared by every extractor in this module — a caller wanting
    both links and text for the same URL calls this (via _fetch_and_parse)
    exactly once, never twice."""
    safe_url = _validate_url(website_url)
    if not safe_url:
        logger.info(f"[SocialLinks] Rejected URL before fetch: {website_url!r}")
        return None

    try:
        headers = {"User-Agent": _USER_AGENT}
        with httpx.Client(follow_redirects=True, timeout=_TIMEOUT_SECONDS, headers=headers) as client:
            with client.stream("GET", safe_url) as resp:
                if resp.status_code != 200:
                    logger.info(f"[SocialLinks] Non-200 ({resp.status_code}) fetching {safe_url}")
                    return None
                chunks = []
                total = 0
                for chunk in resp.iter_bytes():
                    total += len(chunk)
                    chunks.append(chunk)
                    if total > _MAX_RESPONSE_BYTES:
                        logger.info(f"[SocialLinks] {safe_url} exceeded {_MAX_RESPONSE_BYTES}-byte cap, using partial page.")
                        break
                return b"".join(chunks)
    except httpx.TimeoutException:
        logger.info(f"[SocialLinks] Timeout fetching {safe_url}")
        return None
    except httpx.HTTPError as e:
        logger.info(f"[SocialLinks] HTTP error fetching {safe_url}: {e}")
        return None
    except Exception as e:
        logger.warning(f"[SocialLinks] Unexpected error fetching {safe_url}: {e}")
        return None


def _fetch_and_parse(website_url: str) -> Optional[BeautifulSoup]:
    """_fetch_html + BeautifulSoup parse, as the one shared step every public
    extractor below is built on. Returns None on a failed fetch or a parse
    error (logged) — never raises."""
    html_bytes = _fetch_html(website_url)
    if html_bytes is None:
        return None
    try:
        return BeautifulSoup(html_bytes, "html.parser")
    except Exception as e:
        logger.warning(f"[SocialLinks] Parse failure for {website_url}: {e}")
        return None


def _links_from_soup(soup: BeautifulSoup) -> Dict[str, str]:
    """The existing link-extraction logic, unchanged — just factored out so
    it can run against an already-fetched soup."""
    hrefs = [a.get("href") or "" for a in soup.find_all("a", href=True)]

    matched_by_platform: Dict[str, List[str]] = {p: [] for p in SOCIAL_PLATFORMS}
    for href in hrefs:
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        if _is_share_link(href):
            continue
        domain = _href_domain(href)
        if not domain:
            continue
        for platform, domains in _PLATFORM_DOMAINS.items():
            if any(domain == d or domain.endswith("." + d) for d in domains):
                matched_by_platform[platform].append(href)
                break

    result: Dict[str, str] = {}
    for platform, candidates in matched_by_platform.items():
        best = _pick_best(platform, candidates)
        if best:
            result[platform] = _canonicalize(best)
    return result


def _text_from_soup(soup: BeautifulSoup) -> str:
    """Visible-text extraction for the Brand Brief generator: strips
    script/style/nav/footer/head chrome, joins what's left, collapses
    whitespace, and caps length so one oversized page can't blow out a
    prompt."""
    for tag in soup.find_all(_TEXT_STRIP_TAGS):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:_MAX_PAGE_TEXT_CHARS]


def extract_social_links(website_url: str) -> Dict[str, str]:
    """
    Fetches website_url and returns {platform: canonical_profile_url} for
    whichever of SOCIAL_PLATFORMS it could confidently find on the page.
    Never raises: a rejected URL, timeout, non-200, or parse failure all
    return {} (logging the reason), since this result only pre-fills a
    user-verify step and must never block onboarding.
    """
    soup = _fetch_and_parse(website_url)
    if soup is None:
        return {}
    return _links_from_soup(soup)


def _firecrawl_page_text(website_url: str, firecrawl_key: str) -> str:
    """Firecrawl JS-render fallback for extract_page_text: returns the page's
    cleaned markdown (whitespace collapsed, capped), or "" on any failure.
    Reuses the existing firecrawl_service client/key — the same one COMP-VERIFY
    already uses — and adds no new dependency. The URL is run through the same
    SSRF validation as the plain GET before it is handed to Firecrawl."""
    safe_url = _validate_url(website_url)
    if not safe_url:
        return ""
    try:
        from backend.services import firecrawl_service
        content = firecrawl_service.scrape_url(safe_url, firecrawl_key) or ""
    except Exception as e:
        logger.warning(f"[SocialLinks] Firecrawl fallback failed for {safe_url}: {e}")
        return ""
    content = re.sub(r"\s+", " ", content).strip()
    return content[:_MAX_PAGE_TEXT_CHARS]


def extract_page_text(website_url: str, firecrawl_key: Optional[str] = None) -> str:
    """
    Fetches website_url and returns its cleaned visible text (see
    _text_from_soup), for the Brand Brief generator. Never raises: any
    failure returns "" (logging the reason) — this only feeds a best-effort,
    onboarding-time input, and an empty result is always an acceptable
    outcome (the brief generator treats it as "no website evidence").

    When the plain GET yields thin text (below _MIN_USEFUL_TEXT_CHARS — a JS
    shell, a block, or an empty render) AND a firecrawl_key is supplied, falls
    back to a Firecrawl JS-render, which reaches copy a plain GET cannot. The
    richer of the two results wins, so a thin Firecrawl answer never discards a
    usable plain-GET one. With no key, behaviour is exactly as before.
    """
    soup = _fetch_and_parse(website_url)
    text = _text_from_soup(soup) if soup is not None else ""
    if len(text) >= _MIN_USEFUL_TEXT_CHARS or not firecrawl_key:
        return text
    logger.info(
        f"[SocialLinks] Plain GET for {website_url!r} yielded {len(text)} chars "
        f"(< {_MIN_USEFUL_TEXT_CHARS}) — trying Firecrawl JS-render fallback."
    )
    fc_text = _firecrawl_page_text(website_url, firecrawl_key)
    return fc_text if len(fc_text) > len(text) else text


def extract_social_data(website_url: str) -> Tuple[Dict[str, str], str]:
    """
    Returns (links, page_text) from a SINGLE fetch — for a caller that wants
    both link extraction and page text for the same URL without paying for
    two requests (extract_social_links + extract_page_text called separately
    would otherwise each fetch independently).
    """
    soup = _fetch_and_parse(website_url)
    if soup is None:
        return {}, ""
    # _links_from_soup consumes hrefs only; _text_from_soup mutates the tree
    # (decompose), so links must be extracted first from the same soup.
    links = _links_from_soup(soup)
    text = _text_from_soup(soup)
    return links, text
