import os
import sys
import asyncio
import json
from playwright.async_api import async_playwright
import urllib.parse
from datetime import datetime
import re

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

def parse_tweet(tweet_result):
    try:
        core = tweet_result.get("core", {}).get("user_results", {}).get("result", {})
        handle = core.get("legacy", {}).get("screen_name", "")
        
        legacy = tweet_result.get("legacy", {})
        text = legacy.get("full_text", "")
        created_at = legacy.get("created_at", "")
        favorite_count = legacy.get("favorite_count", 0)
        retweet_count = legacy.get("retweet_count", 0)
        reply_count = legacy.get("reply_count", 0)
        
        # Parse media
        media_entities = legacy.get("entities", {}).get("media", [])
        extended_media = legacy.get("extended_entities", {}).get("media", [])
        media_list = extended_media if extended_media else media_entities
        
        media_urls = []
        for m in media_list:
            if m.get("type") == "photo":
                media_urls.append(m.get("media_url_https", ""))
            elif m.get("type") == "video" or m.get("type") == "animated_gif":
                media_urls.append(m.get("media_url_https", "")) # preview image
                
        rest_id = tweet_result.get("rest_id", "")
        url = f"https://x.com/{handle}/status/{rest_id}" if handle and rest_id else ""
        
        return {
            "id": rest_id,
            "text": text,
            "created_at": created_at,
            "favorites": favorite_count,
            "retweets": retweet_count,
            "replies": reply_count,
            "media_urls": [url for url in media_urls if url],
            "url": url
        }
    except Exception as e:
        print(f"Error parsing tweet: {e}")
        return None

def find_tweets_in_json(data):
    tweets = []
    
    def search(node):
        if isinstance(node, list):
            for item in node:
                search(item)
        elif isinstance(node, dict):
            if "tweet_results" in node and "result" in node["tweet_results"]:
                res = node["tweet_results"]["result"]
                # Sometimes it's a TweetWithVisibilityResults
                if res.get("__typename") == "TweetWithVisibilityResults":
                    res = res.get("tweet", {})
                if res.get("__typename") == "Tweet":
                    t = parse_tweet(res)
                    if t and t["id"] not in [x["id"] for x in tweets]:
                        tweets.append(t)
            for v in node.values():
                search(v)
                
    search(data)
    return tweets

def generate_html_report(channel_name, tweets, screenshot_filename):
    cards = ""
    for t in tweets:
        media_html = ""
        if t["media_urls"]:
            # Just show first image
            media_html = f'<div class="img-wrap"><img src="{t["media_urls"][0]}" alt="Media" loading="lazy" /></div>'
            
        text_preview = t["text"]
        # Convert links to actual anchor tags (simple regex)
        text_preview = re.sub(r'(https?://[^\s]+)', r'<a href="\1" target="_blank">\1</a>', text_preview)
        # Convert newlines to br
        text_preview = text_preview.replace('\n', '<br>')
            
        cards += f"""
        <div class="card">
            {media_html}
            <div class="body">
                <div class="text">{text_preview}</div>
                <div class="meta">❤️ {t['favorites']} • 🔁 {t['retweets']} • 💬 {t['replies']}</div>
                <div class="date"><a href="{t['url']}" target="_blank">{t['created_at']}</a></div>
            </div>
        </div>
        """
        
    date_str = datetime.now().strftime("%B %d, %Y")
    screenshot_html = ""
    if screenshot_filename:
        screenshot_html = f"""
        <div class="screenshot-wrap">
            <h2>Profile Landing Page</h2>
            <img src="{screenshot_filename}" alt="Profile Screenshot" style="width: 100%; border-radius: 8px; border: 1px solid #333;" />
        </div>
        """
        
    html = f"""<!DOCTYPE html><html lang="en">
    <head>
        <meta charset="UTF-8"/>
        <title>{channel_name} - X/Twitter Report</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700&display=swap" rel="stylesheet"/>
        <style>
            * {{ box-sizing: border-box; margin: 0; padding: 0; }}
            body {{ background: #000000; font-family: 'Inter', sans-serif; padding: 40px 24px; color: #e7e9ea; }}
            .header {{ max-width: 900px; margin: 0 auto 32px; padding-bottom: 20px; border-bottom: 1px solid #2f3336; }}
            .header h1 {{ font-size: 24px; font-weight: 700; }}
            .header p {{ font-size: 14px; color: #71767b; margin-top: 4px; }}
            .screenshot-wrap {{ max-width: 900px; margin: 0 auto 40px; }}
            h2 {{ max-width: 900px; margin: 0 auto 16px; font-size: 20px; font-weight: 700; }}
            .grid {{ max-width: 900px; margin: 0 auto; display: flex; flex-direction: column; gap: 16px; }}
            .card {{ background: #000000; border: 1px solid #2f3336; border-radius: 16px; overflow: hidden; padding: 16px; }}
            .img-wrap {{ width: 100%; max-height: 400px; background: #16181c; border-radius: 16px; overflow: hidden; margin-bottom: 12px; border: 1px solid #2f3336; }}
            .img-wrap img {{ width: 100%; height: 100%; object-fit: contain; max-height: 400px; }}
            .body {{ display: flex; flex-direction: column; gap: 8px; }}
            .text {{ font-size: 15px; font-weight: 400; line-height: 1.5; color: #e7e9ea; white-space: pre-wrap; }}
            .text a {{ color: #1d9bf0; text-decoration: none; }}
            .text a:hover {{ text-decoration: underline; }}
            .meta {{ font-size: 14px; color: #71767b; display: flex; gap: 16px; margin-top: 8px; }}
            .date {{ font-size: 14px; color: #71767b; margin-top: 4px; }}
            .date a {{ color: #71767b; text-decoration: none; }}
            .date a:hover {{ text-decoration: underline; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>{channel_name}</h1>
            <p>Generated {date_str} · {len(tweets)} tweets</p>
        </div>
        {screenshot_html}
        <h2>Latest Tweets</h2>
        <div class="grid">
            {cards}
        </div>
    </body>
    </html>
    """
    return html

async def run_report(targets, limit=20):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(os.path.dirname(script_dir))
    data_dir = os.path.join(base_dir, "ALL_OUTPUT")
    os.makedirs(data_dir, exist_ok=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = await context.new_page()
        
        # 1. Login Flow
        print("Navigating to X/Twitter login...")
        await page.goto("https://x.com/login")
        
        print("\n⏳ Please log in to your X/Twitter account in the browser.")
        print("The script will automatically detect when you are successfully logged in.")
        
        while True:
            await asyncio.sleep(2)
            url = page.url
            if "login" not in url and "i/flow/login" not in url and url != "https://x.com/":
                # We are logged in and on the home feed
                print("\n✅ Successfully logged in!")
                break
                
        # To store intercepted tweets
        intercepted_tweets = []
        
        async def handle_response(response):
            if "UserTweets" in response.url and response.request.method == "GET":
                try:
                    json_data = await response.json()
                    tweets = find_tweets_in_json(json_data)
                    for t in tweets:
                        if t not in intercepted_tweets:
                            intercepted_tweets.append(t)
                except Exception as e:
                    pass

        page.on("response", handle_response)
        
        for target in targets:
            handle = target.replace("@", "").strip()
            if handle.startswith("http"):
                handle = handle.rstrip("/").split("/")[-1]
                
            base_url = f"https://x.com/{handle}"
            
            print(f"\n--- Processing @{handle} ---")
            print(f"Loading profile: {base_url}")
            
            intercepted_tweets.clear()
            await page.goto(base_url)
            
            # Wait a bit for the API call to fire and images to load
            await asyncio.sleep(4)
            
            screenshot_filename = f"@{handle}_landing.png"
            screenshot_path = os.path.join(data_dir, screenshot_filename)
            await page.screenshot(path=screenshot_path)
            print(f"Saved screenshot to {screenshot_path}")
            
            # Scroll to trigger more tweets if needed
            while len(intercepted_tweets) < limit:
                prev_len = len(intercepted_tweets)
                await page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
                await asyncio.sleep(2)
                if len(intercepted_tweets) == prev_len:
                    break # no more tweets loading
            
            final_tweets = intercepted_tweets[:limit]
            print(f"Extracted {len(final_tweets)} tweets.")
            
            if not final_tweets:
                print(f"❌ No tweets found for @{handle}.")
                continue
                
            html_content = generate_html_report(f"@{handle}", final_tweets, screenshot_filename)
            report_filename = f"@{handle}_twitter.html"
            report_filepath = os.path.join(data_dir, report_filename)
            
            with open(report_filepath, "w", encoding="utf-8") as f:
                f.write(html_content)
                
            file_uri = f"file:///{os.path.abspath(report_filepath).replace(os.sep, '/')}"
            print(f"✅ Python successfully saved the report to: {report_filepath}")
            print(f"🔗 You can open it in your browser using this link: {file_uri}")
                
        await browser.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python twitter_agent.py <handle_or_url1> ...")
        targets = ["@X"]
        print("No targets provided, defaulting to @X")
    else:
        targets = sys.argv[1:]
        
    print(f"Starting X/Twitter JSON scraper for {len(targets)} targets.")
    asyncio.run(run_report(targets, limit=20))
