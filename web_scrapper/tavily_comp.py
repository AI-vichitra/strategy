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

def _research_product_focus(client, brand_name, brand_url, brand_category):
    """
    Quick pre-search + LLM distillation of the brand's actual product focus
    (e.g. "honey and natural foods" rather than a broad category like "FMCG"),
    used to scope the main competitor-search queries more precisely than the
    raw category alone would. Wrapped end-to-end in try/except: ANY failure
    (Tavily error, zero snippets, no LLM provider key, LLM call error, or an
    empty/unusable completion) falls back to brand_category as-is. This is a
    non-blocking refinement, never a dependency the main search can fail on.

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
            return brand_category

        from backend.services.slide_planner import _default_llm_completion

        system_prompt = (
            f"Given these search results about {brand_name} ({brand_url}), identify "
            "their primary product category in 2-5 words. Examples: 'honey and "
            "natural foods', 'electric vehicles', 'cloud hosting services', 'spices "
            "and seasonings'. Return ONLY the product category, nothing else."
        )
        raw = _default_llm_completion(system_prompt, f"Search results:\n{snippets}")
        focus = (raw or "").strip().strip('"').strip("'")
        focus = focus.splitlines()[0].strip() if focus else ""
        return focus or brand_category
    except Exception:
        return brand_category


def search_candidates(brand_name, brand_url, brand_category, industry=None, region=None):
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
    (_research_product_focus) to identify the brand's actual product focus
    (e.g. "electric vehicles" rather than a broad category like "Automotive"),
    which then replaces the broad category as the scoping term in the main
    queries below — any failure in that pre-search falls back to using
    brand_category as-is, so this never blocks the main search.

    Returns {"results": [...], "raw_answers": [...], "product_focus": <str>}.
    A missing TAVILY_API_KEY yields {"results": [], "raw_answers": [],
    "product_focus": None} (handled earlier by the caller, which checks the
    key itself before ever calling this). Within the per-query loop, a query
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

    product_focus = _research_product_focus(client, brand_name, brand_url, brand_category)
    print(f"[COMP-SEARCH] Product focus resolved: '{product_focus}'")
    scope = industry or product_focus
    region_clause = f" in {region}" if region else ""

    queries = [
        f"Top direct competitors and alternatives to the {scope} company '{brand_name}'{region_clause}. Include their official website URLs.",
        f"Companies similar to '{brand_name}' in the {scope} industry{region_clause}, with links to their official websites.",
        f"Who competes with '{brand_name}' in {scope}{region_clause}? Name the competing brands and their own official company websites (not directories, review sites, or listicles).",
    ]

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
    return {"results": all_results, "raw_answers": raw_answers, "product_focus": product_focus}


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
