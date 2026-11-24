"""
Logo Scraper Service
====================
Best-effort, server-side extractor that visits a brand or competitor's website
to extract and download its official logo, saving it to local static storage
(backend/static/uploads/logos/) and returning the relative static URL.

Heuristic tiers:
  1. JSON-LD Schema (Organization / Brand / Corporation / WebSite logo)
  2. OpenGraph & Twitter metadata (og:logo, twitter:image, og:image)
  3. Apple Touch Icon (high-res mobile app icon)
  4. HTML header / navigation logo images
  5. Standard favicon links (<link rel="icon">)
  6. Fallback: Google high-res (128px) favicon service
"""

import os
import re
import json
import uuid
import socket
import logging
import ipaddress
from typing import Dict, List, Optional
from urllib.parse import urlparse, urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_STATIC_LOGOS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "uploads", "logos"
)
os.makedirs(_STATIC_LOGOS_DIR, exist_ok=True)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_FETCH_TIMEOUT_SECONDS = 7.0
_DOWNLOAD_TIMEOUT_SECONDS = 7.0
_MAX_LOGO_SIZE_BYTES = 5 * 1024 * 1024  # 5MB

_IGNORED_IMAGE_PATTERNS = [
    "partner", "client", "sponsor", "footer", "badge", "payment",
    "visa", "mastercard", "amex", "paypal", "stripe", "rating",
    "star", "arrow", "close", "banner", "hero", "avatar", "profile",
    "facebook", "twitter", "linkedin", "instagram", "youtube"
]


def _is_blocked_host(hostname: str) -> bool:
    """SSRF Guard: prevent querying internal/localhost addresses."""
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
    try:
        resolved = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for family, _socktype, _proto, _canon, sockaddr in resolved:
        addr = sockaddr[0]
        try:
            ip = ipaddress.ip_address(addr)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return True
        except ValueError:
            pass
    return False


def get_google_fallback_logo_url(website_url: str) -> str:
    """Returns the Google S2 high-res (128px) favicon URL for the domain."""
    if not website_url:
        return ""
    raw = website_url.strip()
    if not raw.startswith("http://") and not raw.startswith("https://"):
        raw = f"https://{raw}"
    try:
        domain = urlparse(raw).netloc.lower().replace("www.", "")
        if domain:
            return f"https://www.google.com/s2/favicons?domain={domain}&sz=128"
    except Exception:
        pass
    return ""


def _save_image_bytes(content: bytes, content_type: str = "", source_url: str = "") -> Optional[str]:
    """Saves raw image bytes into static uploads directory and returns relative URL."""
    if not content or len(content) < 80 or len(content) > _MAX_LOGO_SIZE_BYTES:
        return None

    ct = (content_type or "").lower()
    src = (source_url or "").lower()

    if "svg" in ct or src.endswith(".svg") or content.strip().startswith(b"<svg") or b"<svg" in content[:200]:
        ext = ".svg"
    elif "png" in ct or src.endswith(".png") or content.startswith(b"\x89PNG"):
        ext = ".png"
    elif "webp" in ct or src.endswith(".webp") or content.startswith(b"RIFF"):
        ext = ".webp"
    elif "x-icon" in ct or "vnd.microsoft.icon" in ct or src.endswith(".ico") or content.startswith(b"\x00\x00\x01\x00"):
        ext = ".ico"
    elif "gif" in ct or src.endswith(".gif") or content.startswith(b"GIF"):
        ext = ".gif"
    elif "jpeg" in ct or "jpg" in ct or src.endswith(".jpg") or src.endswith(".jpeg") or content.startswith(b"\xff\xd8"):
        ext = ".jpg"
    else:
        ext = ".png"

    filename = f"{uuid.uuid4().hex}{ext}"
    dest_path = os.path.join(_STATIC_LOGOS_DIR, filename)
    try:
        with open(dest_path, "wb") as f:
            f.write(content)
        return f"/static/uploads/logos/{filename}"
    except Exception as e:
        logger.warning(f"[LogoScraper] Error writing logo to {dest_path}: {e}")
        return None


def _download_and_persist(url: str, headers: dict) -> Optional[str]:
    """Downloads image from url and persists it locally."""
    try:
        parsed = urlparse(url)
        if _is_blocked_host(parsed.hostname or ""):
            return None
        with httpx.Client(follow_redirects=True, timeout=_DOWNLOAD_TIMEOUT_SECONDS, headers=headers) as client:
            resp = client.get(url)
            if resp.status_code == 200 and len(resp.content) >= 80:
                ct = resp.headers.get("content-type", "")
                return _save_image_bytes(resp.content, content_type=ct, source_url=url)
    except Exception as e:
        logger.debug(f"[LogoScraper] Failed to download candidate logo {url}: {e}")
    return None


def scrape_and_save_logo(website_url: str, brand_name: str = "") -> Optional[str]:
    """
    Main entry point: fetches the target website, finds its logo via multi-tier heuristics,
    downloads and persists it, returning a relative static path (e.g. '/static/uploads/logos/xyz.png').
    Falls back to high-res Google Favicon API if direct extraction fails.
    Never raises an exception.
    """
    if not website_url or not website_url.strip():
        return None

    url = website_url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        url = f"https://{url}"

    parsed = urlparse(url)
    if not parsed.hostname or _is_blocked_host(parsed.hostname):
        return None

    headers = {
        "User-Agent": _USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    candidate_urls: List[str] = []

    try:
        with httpx.Client(follow_redirects=True, timeout=_FETCH_TIMEOUT_SECONDS, headers=headers) as client:
            resp = client.get(url)
            if resp.status_code == 200 and resp.content:
                soup = BeautifulSoup(resp.content, "html.parser")

                # ── Tier 1: JSON-LD Schema ────────────────────────────────────
                for script in soup.find_all("script", type="application/ld+json"):
                    if not script.string:
                        continue
                    try:
                        data = json.loads(script.string)
                        items = data if isinstance(data, list) else [data]
                        for item in items:
                            if not isinstance(item, dict):
                                continue
                            if "@graph" in item and isinstance(item["@graph"], list):
                                items.extend(item["@graph"])
                            logo_val = item.get("logo")
                            if isinstance(logo_val, str) and logo_val.strip():
                                candidate_urls.append(logo_val.strip())
                                break
                            elif isinstance(logo_val, dict) and logo_val.get("url"):
                                candidate_urls.append(str(logo_val["url"]).strip())
                                break
                    except Exception:
                        pass
                    if candidate_urls:
                        break

                # ── Tier 2: OpenGraph & Twitter tags ──────────────────────────
                if not candidate_urls:
                    og_logo = soup.find("meta", property="og:logo") or soup.find("meta", attrs={"name": "og:logo"})
                    if og_logo and og_logo.get("content"):
                        candidate_urls.append(og_logo["content"].strip())

                # ── Tier 3: Apple Touch Icon (high-res square icon) ───────────
                touch_icon = soup.find("link", rel=lambda r: r and any(k in r.lower() for k in ["apple-touch-icon", "apple-touch-icon-precomposed"]))
                if touch_icon and touch_icon.get("href"):
                    candidate_urls.append(touch_icon["href"].strip())

                # ── Tier 4: Header / Nav / Logo Image elements ─────────────────
                img_candidates = soup.select(
                    "header img, nav img, .navbar img, [class*='header'] img, [class*='logo'] img, [id*='logo'] img, a[class*='brand'] img, img[alt*='logo' i], img[src*='logo' i]"
                )
                for img in img_candidates:
                    src = img.get("src") or img.get("data-src") or img.get("data-original")
                    if src and isinstance(src, str) and src.strip():
                        s_lower = src.lower()
                        alt_lower = (img.get("alt") or "").lower()
                        # Exclude obvious non-logo images
                        if any(bad in s_lower or bad in alt_lower for bad in _IGNORED_IMAGE_PATTERNS):
                            continue
                        candidate_urls.append(src.strip())
                        if len(candidate_urls) >= 3:
                            break

                # ── Tier 5: Standard Favicon ──────────────────────────────────
                if not candidate_urls:
                    icon_link = soup.find("link", rel=lambda r: r and "icon" in r.lower())
                    if icon_link and icon_link.get("href"):
                        candidate_urls.append(icon_link["href"].strip())

    except Exception as e:
        logger.debug(f"[LogoScraper] HTML fetch failed for {url}: {e}")

    # Try downloading discovered candidates in order
    for candidate in candidate_urls:
        resolved = urljoin(url, candidate)
        saved = _download_and_persist(resolved, headers)
        if saved:
            logger.info(f"[LogoScraper] Successfully scraped and saved logo for {url} -> {saved}")
            return saved

    # ── Tier 6: High-Res Google Favicon fallback ─────────────────────────────
    fallback_url = get_google_fallback_logo_url(url)
    if fallback_url:
        saved_fallback = _download_and_persist(fallback_url, headers)
        if saved_fallback:
            logger.info(f"[LogoScraper] Cached Google fallback favicon for {url} -> {saved_fallback}")
            return saved_fallback
        return fallback_url

    return None


def scrape_logos_concurrently(items: List[Dict[str, str]], max_workers: int = 5) -> Dict[str, Optional[str]]:
    """
    Scrapes logos for multiple URLs concurrently.
    items: list of dicts with 'url' and optional 'name'.
    Returns mapping: { url: logo_url_or_none }
    """
    results: Dict[str, Optional[str]] = {}
    if not items:
        return results

    urls_to_scrape = []
    for it in items:
        u = it.get("url") or it.get("website_url") or ""
        if u and u not in results:
            urls_to_scrape.append((u, it.get("name") or ""))

    if not urls_to_scrape:
        return results

    with ThreadPoolExecutor(max_workers=min(len(urls_to_scrape), max_workers)) as executor:
        future_to_url = {
            executor.submit(scrape_and_save_logo, u, name): u
            for u, name in urls_to_scrape
        }
        for future in as_completed(future_to_url):
            u = future_to_url[future]
            try:
                results[u] = future.result()
            except Exception as e:
                logger.warning(f"[LogoScraper] Concurrent scrape failed for {u}: {e}")
                results[u] = get_google_fallback_logo_url(u)

    return results
