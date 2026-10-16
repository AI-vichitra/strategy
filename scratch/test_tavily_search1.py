"""
Quick test to see exactly what Tavily Search 1 returns
so we can fix the parsing logic.
Run: backend\venv\Scripts\python.exe scratch\test_tavily_search1.py
"""
import asyncio
import os
import sys

# Load .env
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend", ".env"))
except Exception:
    pass

from tavily import AsyncTavilyClient

async def test():
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        print("ERROR: TAVILY_API_KEY not found")
        return

    client = AsyncTavilyClient(api_key=api_key)

    brand_name = "Apple"
    category = "Technology"

    query = (
        f"Who are the top 3 key business competitors or market rivals of the company "
        f"{brand_name} in the {category} industry? Return only their brand names and official websites."
    )
    print(f"Query: {query}\n")

    response = await client.search(
        query=query,
        search_depth="advanced",
        include_answer=True,
        max_results=5
    )

    print("=== ANSWER ===")
    print(repr(response.get("answer", "")))
    print()
    print("=== RESULTS (urls + titles) ===")
    for r in response.get("results", []):
        print(f"  Title: {r.get('title')}")
        print(f"  URL:   {r.get('url')}")
        print()

asyncio.run(test())
