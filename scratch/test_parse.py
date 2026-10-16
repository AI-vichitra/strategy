"""
Test the parsing logic against the actual Tavily answer.
"""
import re
import json

answer = "Apple's top 3 key competitors are Samsung, Microsoft, and Google. Their official websites are samsung.com, microsoft.com, and google.com."
brand_name = "Apple"

competitors = []

# Try JSON list
if "[" in answer and "]" in answer:
    try:
        json_str = answer[answer.find("["):answer.rfind("]") + 1]
        parsed = json.loads(json_str)
        if isinstance(parsed, list):
            competitors = [str(c).strip() for c in parsed if str(c).strip()]
    except Exception:
        pass
print(f"After JSON parse: {competitors}")

# Fallback: numbered/bullet list
if not competitors:
    matches = re.findall(
        r'(?:^|\n)\s*(?:\d+[\.\)]\s*|[-•*]\s*)([A-Z][A-Za-z0-9\s&\'\.\-]+?)(?:\s*[:\-,]|\s*\n|$)',
        answer
    )
    competitors = [m.strip() for m in matches if len(m.strip()) > 1]
print(f"After bullet regex: {competitors}")

# Fallback: inline mention
if not competitors:
    match = re.search(
        r'(?:include|such as|like|are|competitors include|rivals are|rivals include)\s+([A-Z][A-Za-z0-9,&\'\.\s]+?)(?:\.|$)',
        answer, re.IGNORECASE
    )
    if match:
        parts = re.split(r',\s*|\s+and\s+', match.group(1))
        competitors = [p.strip() for p in parts if len(p.strip()) > 1]
print(f"After inline regex: {competitors}")

# Clean
competitors = list(dict.fromkeys([
    c for c in competitors
    if c and c.lower() not in brand_name.lower() and brand_name.lower() not in c.lower()
]))[:3]
print(f"Final: {competitors}")
