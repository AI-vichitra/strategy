import os
import sys
import re
from dotenv import load_dotenv
from tavily import TavilyClient

def get_insta_handle(brand_name, brand_url, client=None):
    if not client:
        # Provide fallback if called without client
        script_dir = os.path.dirname(os.path.abspath(__file__))
        base_dir = os.path.dirname(script_dir)
        load_dotenv(os.path.join(base_dir, "backend", ".env"))
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            return ""
        client = TavilyClient(api_key=api_key)

    # We search specifically on instagram.com to get the best raw results
    query = f'"{brand_name}" site:instagram.com'
    
    try:
        response = client.search(
            query=query,
            search_depth="basic", # Basic is faster and enough for domain specific searches
            max_results=5,
            include_answer=False # Don't rely on AI generation
        )
        
        for res in response.get("results", []):
            url = res.get("url", "")
            # check if it's a profile URL (not a post, reel, explore, etc)
            match = re.search(r'https?://(?:www\.)?instagram\.com/([^/?#]+)', url)
            if match:
                username = match.group(1).lower()
                # Exclude common non-profile paths
                if username not in ['p', 'reel', 'reels', 'explore', 'tags', 'stories', 'developer', 'about']:
                    return username
                    
        return ""
            
    except Exception as e:
        return ""

if __name__ == "__main__":
    if len(sys.argv) < 3 or len(sys.argv) % 2 == 0:
        print("Usage: python tavily_insta.py <Brand1> <URL1> [<Brand2> <URL2> ...]")
        sys.exit(1)
        
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(script_dir)
    load_dotenv(os.path.join(base_dir, "backend", ".env"))
    
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        print("Error: TAVILY_API_KEY not found in .env!")
        sys.exit(1)

    client = TavilyClient(api_key=api_key)
    
    # Process pairs of brand names and URLs
    args = sys.argv[1:]
    pairs = [(args[i], args[i+1]) for i in range(0, len(args), 2)]
    
    print(f"Fetching Instagram handles for {len(pairs)} brand(s)...\n")
    
    for brand, url in pairs:
        print(f"[{brand}] ({url}) -> ", end="", flush=True)
        handle = get_insta_handle(brand, url, client)
        print(handle)
