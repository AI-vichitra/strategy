import os
import re

html_path = r"c:\Users\Cog\Desktop\Strategy\docs\project_scrapped\skybags_scrapped\inskybags_insta.html"
try:
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
        print(f"Read {len(html_content)} bytes")
        cards = re.findall(r'<div class="card">(.*?)</div></div>', html_content, re.DOTALL)
        print(f"Found {len(cards)} cards")
        
        if cards:
            for idx, card in enumerate(cards[:2]):
                text_content = re.sub(r'<[^>]+>', ' ', card)
                text_content = re.sub(r'\s+', ' ', text_content).strip()
                print(f"Post {idx+1}: {text_content[:200]}")
        else:
            print("No cards found, using fallback")
            html_content_clean = re.sub(r'<style[^>]*>[\s\S]*?</style>', ' ', html_content, flags=re.IGNORECASE)
            html_content_clean = re.sub(r'<script[^>]*>[\s\S]*?</script>', ' ', html_content, flags=re.IGNORECASE)
            text_content = re.sub(r'<[^>]+>', ' ', html_content_clean)
            text_content = re.sub(r'\s+', ' ', text_content).strip()
            print(f"Fallback text: {text_content[:200]}")
            
except Exception as e:
    print(f"Error: {e}")
