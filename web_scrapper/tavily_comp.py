import os
import sys
import re
from collections import Counter
from urllib.parse import urlparse
from dotenv import load_dotenv
from tavily import TavilyClient

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
