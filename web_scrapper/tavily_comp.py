import os
import sys
import re
from collections import Counter
from urllib.parse import urlparse
from dotenv import load_dotenv
from tavily import TavilyClient

# Directory/aggregator/news domains that answer "who competes with X" without
# being a competitor's own site. get_competitors() below has always excluded
# a short version of this inline; search_candidates() reuses the same idea
# (extended) so the LLM resolver sees more genuine company sites within its
# small per-query result cap, instead of spending slots on sites like these.
_DIRECTORY_DOMAIN_DENYLIST = (
    "growjo.com", "crunchbase.com", "zoominfo.com", "linkedin.com", "g2.com",
    "glassdoor.com", "clutch.co", "goodfirms.co", "forbes.com", "bloomberg.com",
    "cbinsights.com", "tracxn.com", "rocketreach.co", "owler.com", "craft.co",
    "apistemic.com", "latterly.org",
    "facebook.com", "reddit.com", "wikipedia.org", "quora.com", "youtube.com",
    "businesswire.com", "prnewswire.com", "globenewswire.com",
    "semrush.com", "similarweb.com",
    "imarcgroup.com", "researchandmarkets.com", "grandviewresearch.com", "marketsandmarkets.com",
    "capterra.com", "techcrunch.com",
)

# ── Backend-owned metro expansion (single source) ────────────────────────────
# A city with no mapping here simply expands to itself (see _expand_to_metro).
# Lookup is case-insensitive; keys are lowercase.
METRO_EXPANSION = {
    "gurugram": "Delhi NCR", "gurgaon": "Delhi NCR", "noida": "Delhi NCR",
    "delhi": "Delhi NCR", "new delhi": "Delhi NCR", "faridabad": "Delhi NCR",
    "ghaziabad": "Delhi NCR",
    "mumbai": "Mumbai Metropolitan Region", "navi mumbai": "Mumbai Metropolitan Region",
    "thane": "Mumbai Metropolitan Region",
    "bangalore": "Bengaluru", "bengaluru": "Bengaluru",
    "san francisco": "San Francisco Bay Area", "oakland": "San Francisco Bay Area",
    "san jose": "San Francisco Bay Area", "palo alto": "San Francisco Bay Area",
    "new york": "New York Metropolitan Area", "brooklyn": "New York Metropolitan Area",
    "jersey city": "New York Metropolitan Area",
    "london": "Greater London",
}


def _expand_to_metro(city: str) -> str:
    """A city with no mapping expands to itself, unchanged."""
    return METRO_EXPANSION.get(city.strip().lower(), city.strip())


def _build_place_terms(target_market):
    """
    Builds geography PLACE TERMS from a normalized target_market dict
    ({"region", "cities", "custom_region"} — see
    backend.schemas.brand.normalize_target_market), metro-expanding every
    city. Returns [] when there is nothing to narrow by (global, or no
    target_market at all) — callers must treat an empty list as "broaden
    only, no geo narrowing", never as an error.

      global                      -> [] (no geo terms)
      local                       -> the typed cities, each metro-expanded
      india/us/europe + cities    -> those cities, each metro-expanded
      india/us/europe, no cities  -> [region] (caller adds the Fix C
                                      city-inference fallback on top)
      other                       -> [custom_region] + any cities, metro-expanded
      unrecognized/legacy string  -> [region] as a raw geography term, so a
                                      free-text legacy value (e.g. "Rajasthan")
                                      still narrows exactly as it did before
                                      this pass
    """
    if not target_market:
        return []

    region = (target_market.get("region") or "").strip().lower()
    cities = [c.strip() for c in (target_market.get("cities") or []) if c and c.strip()]
    custom_region = (target_market.get("custom_region") or "").strip()

    if region == "global":
        return []

    if region == "local":
        terms = [_expand_to_metro(c) for c in cities]
    elif region in ("india", "us", "europe"):
        terms = [_expand_to_metro(c) for c in cities] if cities else ([region] if region else [])
    elif region == "other":
        terms = ([custom_region] if custom_region else []) + [_expand_to_metro(c) for c in cities]
    elif region:
        # Unrecognized region string (legacy free text) — use as-is.
        terms = [region]
    else:
        terms = []

    # Dedupe while preserving order (metro-expansion can collapse several
    # cities onto the same metro name).
    seen = set()
    deduped = []
    for t in terms:
        key = t.lower()
        if t and key not in seen:
            seen.add(key)
            deduped.append(t)
    return deduped


class CompetitorDiscoveryFailure(Exception):
    """Raised by search_candidates() when every per-query Tavily call in the
    loop raised an exception (search genuinely broke), as opposed to a query
    succeeding but simply returning zero results (a legitimate empty
    outcome). backend.services.competitor_service re-exports this class from
    here (rather than this module importing from there) so tavily_comp.py's
    standalone CLI usage below never needs backend's package path on
    sys.path at import time.
    """
    pass


def get_competitors(brand_name, brand_url, brand_category):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(script_dir)
    # The .env file is located in the backend folder
    load_dotenv(os.path.join(base_dir, "backend", ".env"))
    
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        print("Error: TAVILY_API_KEY not found in .env!")
        return []

    client = TavilyClient(api_key=api_key)
    
    # Let Tavily answer naturally without forcing a strict format
    queries = [
        f"Find top 5 alternatives and direct competitors to the {brand_category} company '{brand_name}' ({brand_url}). Provide their official website URLs starting with https://",
        f"What are 5 similar {brand_category} companies/agencies to '{brand_name}'? Please include links to their official websites (starting with https://).",
        f"List the biggest business competitors of '{brand_name}'. Include their full website URLs (starting with https://) in the response."
    ]
    
    print(f"Deep analyzing competitors for {brand_name.upper()} ({brand_category}) across multiple queries...\n")
    
    all_competitor_urls = []
    raw_answers = []
    
    for i, query in enumerate(queries, 1):
        try:
            response = client.search(
                query=query,
                search_depth="advanced",
                include_answer=True
            )
            answer = response.get("answer", "")
            if answer:
                raw_answers.append(answer)
            # Extract domains directly from the natural language answer
            potential_domains = re.findall(r'\b(?:https?://)?(?:www\.)?([a-zA-Z0-9\-]+\.[a-zA-Z]{2,}(?:\.[a-zA-Z]{2,})?)\b', answer)
            
            # Ensure brand_url has a scheme for proper parsing
            parsed_brand_url = brand_url if brand_url.startswith('http') else 'http://' + brand_url
            brand_domain = urlparse(parsed_brand_url).netloc.lower().replace("www.", "")
            
            for domain in potential_domains:
                domain = domain.lower()
                url = f"https://www.{domain}"
                
                # Exclude common directory/news sites
                if any(x in domain for x in ['growjo.com', 'crunchbase.com', 'zoominfo.com', 'linkedin.com', 'g2.com', 'glassdoor.com', 'clutch.co', 'goodfirms.co', 'forbes.com', 'bloomberg.com']):
                    continue
                    
                # Exclude the original brand itself
                if brand_domain and brand_domain in domain:
                    continue
                    
                all_competitor_urls.append(url)
                
        except Exception as e:
            pass
            
    if not all_competitor_urls:
        print("Could not find any valid competitor URLs in Tavily's answers.")
        return []
        
    # Count frequency by domain
    domain_counts = Counter()
    domain_to_url = {}
    
    for url in all_competitor_urls:
        domain = urlparse(url).netloc.lower().replace("www.", "")
        domain_counts[domain] += 1
        domain_to_url[domain] = url
            
    # Sort by frequency
    top_domains = [domain for domain, count in domain_counts.most_common(5)]
    
    results = []
    for domain in top_domains:
        brand_name_from_domain = domain.split('.')[0].capitalize()
        url = domain_to_url[domain]
        # Basic handle derivation from name
        handle = re.sub(r'[^\w]', '', brand_name_from_domain.lower())
        results.append({
            "name": brand_name_from_domain,
            "website_url": url,
            "handle": handle,
            "source": "tavily"
        })
        
    return results

def _extract_json_object(text):
    """Best-effort JSON object parse: strips a ```fence``` if present, then
    falls back to the first {...} span. Returns None (never raises) on any
    failure, so callers can treat it the same as a missing/unusable response."""
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
        cleaned = re.sub(r"```\s*$", "", cleaned).strip()
    try:
        import json
        data = json.loads(cleaned)
    except Exception:
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not m:
            return None
        try:
            import json
            data = json.loads(m.group(0))
        except Exception:
            return None
    return data if isinstance(data, dict) else None


def _research_brand_scope(client, brand_name, brand_url, brand_category):
    """
    Quick pre-search + single LLM distillation of three things about the
    TARGET brand, all grounded in the SAME pre-search snippets about the
    brand's own site/content (no extra Tavily call beyond what this already
    made as _research_product_focus):
      1. product_focus — the brand's actual product focus (e.g. "honey and
         natural foods" rather than a broad category like "FMCG").
      2. segment — market segment/tier (e.g. "premium/luxury", "budget
         mass-market", "boutique/artisanal"), or "unknown" when the fetched
         content doesn't clearly support one — never guessed.
      3. geography — primary operating region/market, or "unknown" when the
         content doesn't clearly indicate one — never guessed.
    Used to scope the main competitor-search queries more precisely than the
    raw category alone would. Wrapped end-to-end in try/except: ANY failure
    (Tavily error, zero snippets, no LLM provider key, LLM call error, an
    empty/unusable completion, or unparseable JSON) falls back to
    (brand_category, "unknown", "unknown"). This is a non-blocking
    refinement, never a dependency the main search can fail on.

    The lazy `backend.services.slide_planner` import relies on the project
    root already being on sys.path — true whenever this runs via its only
    real caller, search_candidates(), which itself is only ever invoked from
    backend/services/competitor_service.py's discover_and_resolve(), whose
    module-level code inserts the project root at import time.
    """
    try:
        response = client.search(
            query=f"{brand_name} products services what does {brand_name} do",
            search_depth="basic",
            max_results=3,
        )
        snippets = "\n".join(
            r.get("content", "") for r in (response.get("results", []) or []) if r.get("content")
        )
        if not snippets:
            return brand_category, "unknown", "unknown"

        from backend.services.slide_planner import _default_llm_completion

        system_prompt = (
            f"Given these search results about {brand_name} ({brand_url}), identify three "
            "things, grounded ONLY in what this text actually supports — never guess:\n"
            "1. product_focus: their primary product category in 2-5 words. Examples: "
            "'honey and natural foods', 'electric vehicles', 'cloud hosting services', "
            "'spices and seasonings'.\n"
            "2. segment: their market segment/tier in 2-4 words, e.g. 'premium/luxury', "
            "'budget mass-market', 'mid-market B2B SaaS', 'boutique/artisanal'. Return "
            "exactly the string \"unknown\" if the text doesn't clearly support one.\n"
            "3. geography: their primary operating region or market in 2-4 words, e.g. "
            "'India', 'United States', 'Southeast Asia', 'Western Europe'. Return exactly "
            "the string \"unknown\" if the text doesn't clearly indicate one.\n"
            "Return ONLY a JSON object, nothing else: "
            '{"product_focus": "...", "segment": "...", "geography": "..."}'
        )
        raw = _default_llm_completion(system_prompt, f"Search results:\n{snippets}")
        data = _extract_json_object(raw)
        if not data:
            return brand_category, "unknown", "unknown"

        focus = str(data.get("product_focus") or "").strip() or brand_category
        segment = str(data.get("segment") or "").strip() or "unknown"
        geography = str(data.get("geography") or "").strip() or "unknown"
        return focus, segment, geography
    except Exception:
        return brand_category, "unknown", "unknown"


def search_candidates(brand_name, brand_url, brand_category, industry=None, region=None, target_market=None):
    """
    Structured-results variant used by the LLM-resolver path
    (backend/services/competitor_service.py). Unlike get_competitors() above —
    which regex-parses Tavily's natural-language `answer` and is left fully
    untouched for the regression-safe legacy fallback — this scopes the
    discovery queries with industry/region/product-focus and returns Tavily's
    STRUCTURED per-hit results (one entry per search hit: title, url, snippet,
    domain), so the LLM resolver can judge/ground against real URLs instead of
    free text.

    Before building the main queries, runs a quick pre-search + LLM step
    (_research_brand_scope) to identify the brand's actual product focus
    (e.g. "electric vehicles" rather than a broad category like "Automotive"),
    market segment/tier, and primary geography — product_focus replaces the
    broad category as the scoping term in the main queries below; segment
    adds an EXTRA scoped query variant alongside the broad ones, never
    replacing them. Any failure in that pre-search falls back to
    (brand_category, "unknown", "unknown"), so this never blocks the main
    search.

    `target_market` is the NORMALIZED structured shape (see
    backend.schemas.brand.normalize_target_market — the caller normalizes
    before calling this, whether the original input was the new structured
    object or a legacy bare `region` string): {"region", "cities",
    "custom_region"}. Its cities (metro-expanded via _build_place_terms /
    METRO_EXPANSION) drive the geography-scoped query variants below. The
    inferred `geography` above is now a FALLBACK ONLY, used solely when a
    region is set but no cities were given (and region isn't global/local) —
    it never overrides an explicit city/region/custom_region.

    Returns {"results": [...], "raw_answers": [...], "product_focus": <str>,
    "segment": <str>, "geography": <str>}. A missing TAVILY_API_KEY yields
    {"results": [], "raw_answers": [], "product_focus": None} (no segment/
    geography keys — handled earlier by the caller, which checks the key
    itself before ever calling this). Within the per-query loop, a query
    that raises is caught and skipped so the others still run; but if EVERY
    query raises, that is a genuine search failure, not an empty result, so
    this raises CompetitorDiscoveryFailure instead of silently returning an
    empty list. If at least one query completed (even with zero results after
    filtering), this returns normally with whatever was collected.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(script_dir)
    load_dotenv(os.path.join(base_dir, "backend", ".env"))

    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return {"results": [], "raw_answers": [], "product_focus": None}

    client = TavilyClient(api_key=api_key)

    print(f"[COMP-SEARCH] Starting search for brand='{brand_name}', category='{brand_category}', region='{region}'")

    product_focus, segment, geography = _research_brand_scope(client, brand_name, brand_url, brand_category)
    print(f"[COMP-SEARCH] Product focus resolved: '{product_focus}', segment='{segment}', geography='{geography}'")
    scope = industry or product_focus
    region_clause = f" in {region}" if region else ""

    queries = [
        f"Top direct competitors and alternatives to the {scope} company '{brand_name}'{region_clause}. Include their official website URLs.",
        f"Companies similar to '{brand_name}' in the {scope} industry{region_clause}, with links to their official websites.",
        f"Who competes with '{brand_name}' in {scope}{region_clause}? Name the competing brands and their own official company websites (not directories, review sites, or listicles).",
    ]

    # ── ADDITIVE segment + geography-scoped variants ───────────────────────
    # Added ALONGSIDE the broad queries above, never replacing them — no
    # place terms (global, or no target_market at all) only means no geo
    # variant gets added, so coverage can only broaden here, never wrongly
    # narrow.
    place_terms = _build_place_terms(target_market)

    tm_region = (target_market.get("region") or "").strip().lower() if target_market else ""
    tm_cities = [c for c in (target_market.get("cities") or []) if c and c.strip()] if target_market else []

    # Fix C city-inference FALLBACK ONLY: consulted solely when a region is
    # set, no cities were given, and the region isn't global/local — never
    # overrides an explicit city/region/custom_region already in place_terms.
    if target_market and tm_region not in ("", "global", "local") and not tm_cities:
        if geography and geography != "unknown" and geography.lower() not in [t.lower() for t in place_terms]:
            place_terms.append(geography)

    if segment != "unknown":
        geo_clause = f" in {place_terms[0]}" if place_terms else ""
        queries.append(
            f"Direct competitors of '{brand_name}' in the {segment} segment of the "
            f"{scope} industry{geo_clause}. Include their official website URLs."
        )

    # One city/geography-scoped query per place term, capped at 3.
    MAX_GEO_QUERIES = 3
    for term in place_terms[:MAX_GEO_QUERIES]:
        queries.append(
            f"Who competes with '{brand_name}' specifically in {term}? Name "
            f"{scope} companies operating in {term}, with their official "
            f"website URLs."
        )

    all_results = []
    raw_answers = []
    seen_urls = set()
    seen_domains = set()
    failed_queries = 0

    for query in queries:
        try:
            response = client.search(
                query=query,
                search_depth="advanced",
                max_results=8,
                include_answer=True,
            )
        except Exception:
            failed_queries += 1
            continue

        answer = response.get("answer", "") or ""
        if answer:
            raw_answers.append(answer)

        query_results = response.get("results", []) or []
        print(f"[COMP-SEARCH] Query: '{query}' → {len(query_results)} results")
        for r in query_results:
            print(f"[COMP-SEARCH]   - {r.get('title','')} | {r.get('url','')}")

        for r in query_results:
            url = r.get("url", "")
            if not url or url in seen_urls:
                continue
            domain = urlparse(url).netloc.lower().replace("www.", "")
            # Same directory/aggregator denylist get_competitors() already
            # excludes above — skip them here too so the LLM resolver sees a
            # higher ratio of genuine company sites within the per-query cap.
            if any(d in domain for d in _DIRECTORY_DOMAIN_DENYLIST):
                continue
            seen_urls.add(url)
            if domain in seen_domains:
                continue
            seen_domains.add(domain)
            all_results.append({
                "title": r.get("title", ""),
                "url": url,
                "snippet": r.get("content", ""),
                "domain": domain,
            })

    if failed_queries == len(queries):
        raise CompetitorDiscoveryFailure("All Tavily search queries failed")

    print(f"[COMP-SEARCH] Returning {len(all_results)} raw candidates")
    return {
        "results": all_results,
        "raw_answers": raw_answers,
        "product_focus": product_focus,
        "segment": segment,
        "geography": geography,
    }


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python tavily_comp.py <brand_name> <brand_url> <brand_category>")
        sys.exit(1)
        
    brand_name = sys.argv[1]
    brand_url = sys.argv[2]
    brand_category = sys.argv[3]
    
    comps = get_competitors(brand_name, brand_url, brand_category)
    for i, c in enumerate(comps, 1):
        print(f"{i}. {c['name']} ({c['website_url']})")
