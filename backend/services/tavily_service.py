"""
Tavily Service
==============
Wraps the Tavily API for:
  1. Competitor discovery (search_competitors)
  2. Brand web scrape — saves rich HTML to docs folder (run_web_scrape)
  3. Deep dive research — saves comprehensive HTML to docs folder (run_deep_dive)
  4. Social handle discovery (find_social_handle)
"""

import os
import re
import html as html_lib
import json
import logging
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

# ── Lazy import Tavily client ─────────────────────────────────────────────────
def _get_client():
    from tavily import TavilyClient
    api_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key:
        raise RuntimeError("TAVILY_API_KEY not set in environment")
    return TavilyClient(api_key=api_key)


# ── 1. Competitor Discovery ───────────────────────────────────────────────────
def search_competitors(
    brand_name: str,
    category: str,
    website_url: str,
    user_competitors: Optional[List[Dict]] = None
) -> Dict[str, Any]:
    """
    Uses Tavily to find competitors for a given brand.
    Returns dict:  { candidates: [{name, website_url, handle, source}], brand_handle, tavily_error }
    """
    import sys
    # Ensure web_scrapper is in path
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        
    try:
        from web_scrapper import tavily_comp
        candidates = tavily_comp.get_competitors(brand_name, website_url, category)
        tavily_error = ""
    except Exception as e:
        candidates = []
        tavily_error = str(e)
        logger.warning(f"Tavily competitor search failed: {e}")

    # --- Discover brand's own social handle ---
    brand_handle = ""
    try:
        from web_scrapper import tavily_insta
        brand_handle = tavily_insta.get_insta_handle(brand_name, website_url)
    except Exception as e:
        logger.warning(f"Brand handle discovery failed: {e}")

    # --- Merge user-provided competitors ---
    if user_competitors:
        existing_names = {c["name"].lower() for c in candidates}
        for uc in user_competitors:
            if uc.get("name") and uc["name"].lower() not in existing_names:
                candidates.append({
                    "name": uc["name"],
                    "website_url": uc.get("url") or "",
                    "handle": _url_to_handle(uc.get("url") or uc["name"]),
                    "source": "user"
                })

    return {
        "candidates": candidates[:8],
        "brand_handle": brand_handle,
        "tavily_error": tavily_error
    }


# ── 2. Brand Web Scrape → saves JSON ────────────────────────────────────────
def run_web_scrape(brand_name: str, brand_url: str, output_dir: str) -> Optional[str]:
    """
    Runs a comprehensive web search and saves a structured JSON document to output_dir.
    JSON format: { title, url, source_type, brand, content }
    Returns the file path, or None on failure.
    """
    try:
        client = _get_client()
    except RuntimeError as e:
        logger.error(f"Web scrape skipped: {e}")
        return None

    os.makedirs(output_dir, exist_ok=True)
    clean_name = re.sub(r'[^\w]', '_', brand_name.lower())

    queries = [
        f"What is {brand_name}? overview, history, and company summary",
        f"{brand_name} products and services comprehensive list",
        f"{brand_name} pricing model and revenue streams",
        f"{brand_name} latest news and announcements 2025",
        f"{brand_name} customer reviews and reputation",
    ]

    all_content_parts = []
    all_sources = []

    for query in queries:
        try:
            resp = client.search(query=query, search_depth="basic", max_results=3, include_answer=True)
            answer = resp.get("answer", "") or ""
            results = resp.get("results", [])
            if answer:
                all_content_parts.append(answer)
            for r in results:
                all_content_parts.append(r.get("content", ""))
                all_sources.append({"title": r.get("title", ""), "url": r.get("url", "")})
        except Exception as e:
            logger.warning(f"Web scrape query failed: {e}")

    doc = {
        "title": f"{brand_name} — Web Intelligence Report",
        "url": brand_url,
        "source_type": "web_scrape",
        "brand": brand_name,
        "content": "\n\n".join(filter(None, all_content_parts)),
        "sources": all_sources,
    }

    filepath = os.path.join(output_dir, f"{clean_name}_web.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    logger.info(f"Web scrape saved to {filepath}")
    return filepath


# ── 3. Deep Dive → saves JSON ─────────────────────────────────────────────────
def run_deep_dive(brand_name: str, brand_url: str, brand_category: str, output_dir: str) -> Optional[str]:
    """
    Runs the comprehensive 4-category deep research and saves a structured JSON document.
    JSON format: { title, url, source_type, brand, content, sections }
    Returns the file path, or None on failure.
    """
    import sys
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        
    try:
        from web_scrapper import tavily_web
        html_filepath = tavily_web.run_report(brand_name, brand_url, brand_category, output_dir=output_dir)
        
        if html_filepath and os.path.exists(html_filepath):
            with open(html_filepath, "r", encoding="utf-8", errors="ignore") as f:
                raw_html = f.read()
            import re
            # Remove <style> and <script> blocks entirely
            raw_html = re.sub(r'<style[^>]*>.*?</style>', ' ', raw_html, flags=re.DOTALL | re.IGNORECASE)
            raw_html = re.sub(r'<script[^>]*>.*?</script>', ' ', raw_html, flags=re.DOTALL | re.IGNORECASE)
            
            text_content = re.sub(r'<[^>]+>', ' ', raw_html)
            text_content = re.sub(r'\s+', ' ', text_content).strip()
            
            doc = {
                "title": f"{brand_name} — Deep Intelligence Report",
                "url": brand_url,
                "source_type": "deep_dive",
                "brand": brand_name,
                "category": brand_category,
                "content": text_content,
                "sections": {}
            }
            clean_name = brand_name.replace(" ", "_").lower()
            json_filepath = os.path.join(output_dir, f"{clean_name}_tavily2.json")
            with open(json_filepath, "w", encoding="utf-8") as f:
                json.dump(doc, f, ensure_ascii=False, indent=2)
            logger.info(f"Deep dive JSON saved to {json_filepath}")
            return json_filepath
            
        return html_filepath
    except Exception as e:
        logger.error(f"Deep dive skipped: {e}")
        return None


# ── 4. Social Handle Discovery ────────────────────────────────────────────────
def find_social_handle(brand_name: str, brand_url: str = "") -> str:
    """
    Uses Tavily to discover the official Instagram handle for a brand.
    Returns the handle string (without @), or empty string on failure.
    """
    import sys
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        
    try:
        from web_scrapper import tavily_insta
        return tavily_insta.get_insta_handle(brand_name, brand_url)
    except Exception as e:
        logger.warning(f"Social handle discovery failed for '{brand_name}': {e}")
        return ""


# ── Helpers ───────────────────────────────────────────────────────────────────
def _discover_handle(client, brand_name: str) -> str:
    query = f"What is the official Instagram handle or username of {brand_name}? site:instagram.com"
    try:
        resp = client.search(query=query, search_depth="basic", max_results=3, include_answer=True)
        # Check results for instagram.com URLs
        for r in resp.get("results", []):
            url = r.get("url", "")
            m = re.search(r'instagram\.com/([A-Za-z0-9_.]+)', url)
            if m:
                handle = m.group(1).rstrip(". /")
                if handle.lower() not in ("p", "explore", "reel", "stories", "reels"):
                    return handle
        # Fallback: parse answer text
        answer = resp.get("answer", "") or ""
        m = re.search(r'@([A-Za-z0-9_.]+)', answer)
        if m:
            return m.group(1).rstrip(". /")
        m = re.search(r'instagram\.com/([A-Za-z0-9_.]+)', answer)
        if m:
            return m.group(1).rstrip(". /")
    except Exception as e:
        logger.warning(f"Handle discovery error: {e}")
    # Final fallback: slug from brand name
    return re.sub(r'[^\w]', '', brand_name.lower())


def _extract_company_name(title: str, brand_name: str) -> str:
    """Extract a clean company name from a search result title."""
    # Common suffixes to strip
    title = re.sub(r'\s*[-|–]\s*.+$', '', title).strip()
    title = re.sub(r'\b(Inc|Ltd|LLC|Corp|Co|GmbH|PLC|SA|AG)\b\.?', '', title, flags=re.IGNORECASE).strip()
    # Don't return if it's too long (likely a headline, not a name)
    if len(title) > 50:
        words = title.split()
        title = " ".join(words[:3])
    return title.strip() if title else ""


def _url_to_handle(url: str) -> str:
    """Convert a website URL to a likely Instagram handle."""
    if not url:
        return ""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url if url.startswith("http") else "https://" + url)
        domain = parsed.netloc or parsed.path
        handle = domain.replace("www.", "").split(".")[0]
        return re.sub(r'[^\w]', '', handle.lower())
    except Exception:
        return ""


def _clean_url(url: str) -> str:
    """Return just the root domain URL."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else url
    except Exception:
        return url


def _user_comps_to_candidates(user_competitors):
    if not user_competitors:
        return []
    return [
        {"name": uc.get("name", ""), "website_url": uc.get("url", ""), "handle": "", "source": "user"}
        for uc in user_competitors if uc.get("name")
    ]


def _parse_competitors_from_text(text: str, brand_name: str) -> list:
    """Try to extract competitor names from an answer paragraph."""
    candidates = []
    lines = text.split("\n")
    for line in lines:
        line = line.strip().lstrip("0123456789.-) ")
        if len(line) > 2 and len(line) < 60 and brand_name.lower() not in line.lower():
            candidates.append({
                "name": line,
                "website_url": "",
                "handle": re.sub(r'[^\w]', '', line.lower()),
                "source": "tavily"
            })
    return candidates[:5]


def _build_simple_html_report(brand_name: str, brand_url: str, categorized_results: dict) -> str:
    sections = ""
    for cat, data in categorized_results.items():
        answer = data.get("answer", "")
        results = data.get("results", [])
        results_html = ""
        for r in results:
            title = html_lib.escape(r.get("title", ""))
            url = r.get("url", "#")
            content = html_lib.escape(r.get("content", "")[:400])
            results_html += f'<div class="card"><h3><a href="{url}" target="_blank">{title}</a></h3><p>{content}</p></div>'
        answer_html = f'<div class="answer">{html_lib.escape(answer)}</div>' if answer else ""
        sections += f'<section><h2>{html_lib.escape(cat)}</h2>{answer_html}{results_html}</section>'

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>{html_lib.escape(brand_name)} - Web Intelligence</title>
<style>body{{font-family:sans-serif;background:#0b0c10;color:#e2e8f0;padding:32px;}}
h1{{color:#00f2fe;}} h2{{color:#4facfe;border-bottom:1px solid #333;padding-bottom:8px;}}
.answer{{background:#1e2130;border-left:3px solid #00f2fe;padding:12px;margin:12px 0;border-radius:4px;}}
.card{{background:#16181c;border:1px solid #2a2d3a;border-radius:8px;padding:16px;margin:12px 0;}}
a{{color:#00f2fe;}} a:hover{{text-decoration:underline;}}</style></head>
<body><h1>{html_lib.escape(brand_name)}</h1>
<p><a href="{html_lib.escape(brand_url)}">{html_lib.escape(brand_url)}</a></p>
{sections}</body></html>"""


def _build_deep_dive_html_report(brand_name: str, brand_url: str, category: str, categorized_results: dict) -> str:
    sections = ""
    for cat, data in categorized_results.items():
        answer = data.get("answer", "")
        results = data.get("results", [])
        formatted_title = cat.replace("_", " ").title()
        results_html = ""
        for r in results:
            title = html_lib.escape(r.get("title", ""))
            url = r.get("url", "#")
            content = html_lib.escape(r.get("content", "")[:600])
            results_html += f'<div class="card"><h3><a href="{url}" target="_blank">{title}</a></h3><p>{content}</p></div>'
        answer_html = f'<div class="answer">{html_lib.escape(answer)}</div>' if answer else ""
        sections += f'<section><h2>{html_lib.escape(formatted_title)}</h2>{answer_html}{results_html}</section>'

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>{html_lib.escape(brand_name)} - Deep Intelligence Report</title>
<style>body{{font-family:sans-serif;background:#0b0c10;color:#e2e8f0;padding:32px;}}
h1{{color:#00f2fe;font-size:2rem;}} h2{{color:#4facfe;border-bottom:1px solid #333;padding-bottom:8px;margin-top:40px;}}
.answer{{background:#1e2130;border-left:3px solid #00f2fe;padding:16px;margin:16px 0;border-radius:4px;line-height:1.7;}}
.card{{background:#16181c;border:1px solid #2a2d3a;border-radius:8px;padding:16px;margin:12px 0;}}
.tag{{display:inline-block;background:#7c3aed22;color:#a78bfa;padding:2px 8px;border-radius:99px;font-size:12px;margin-bottom:8px;}}
a{{color:#00f2fe;}} a:hover{{text-decoration:underline;}}</style></head>
<body>
<h1>{html_lib.escape(brand_name)}</h1>
<span class="tag">{html_lib.escape(category)}</span>
<p><a href="{html_lib.escape(brand_url)}">{html_lib.escape(brand_url)}</a></p>
{sections}</body></html>"""
