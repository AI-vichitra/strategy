import os
import sys
import asyncio
import json
from playwright.async_api import async_playwright
import urllib.parse
from datetime import datetime

# Force utf-8 output to avoid UnicodeEncodeError in Windows cmd
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

def find_keys(node, key):
    """Recursively search for a key in a nested dict/list."""
    if isinstance(node, list):
        for item in node:
            yield from find_keys(item, key)
    elif isinstance(node, dict):
        if key in node:
            yield node[key]
        for v in node.values():
            yield from find_keys(v, key)

def parse_lockup_view_model(renderer, is_short=False):
    try:
        videoId = renderer.get("contentId", "")
        if not videoId: return None
        
        # Title
        meta = renderer.get("metadata", {}).get("lockupMetadataViewModel", {})
        title = meta.get("title", {}).get("content", "")
        
        # Thumbnail
        thumbnails = renderer.get("contentImage", {}).get("thumbnailViewModel", {}).get("image", {}).get("sources", [])
        thumb_url = thumbnails[-1].get("url", "") if thumbnails else ""
        
        # Views and Time
        view_text = ""
        time_text = ""
        parts = meta.get("metadata", {}).get("contentMetadataViewModel", {}).get("metadataRows", [{}])[0].get("metadataParts", [])
        if len(parts) >= 1:
            view_text = parts[0].get("text", {}).get("content", "")
        if len(parts) >= 2:
            time_text = parts[1].get("text", {}).get("content", "")
            
        return {
            "title": title,
            "url": f"https://www.youtube.com/shorts/{videoId}" if is_short else f"https://www.youtube.com/watch?v={videoId}",
            "thumb": thumb_url,
            "views": view_text,
            "time": time_text
        }
    except Exception:
        return None

def parse_shorts_lockup_view_model(renderer):
    try:
        # ID is usually embedded in entityId like "shorts-shelf-item-e1ihd4ZtiBY" or similar
        entity_id = renderer.get("entityId", "")
        videoId = entity_id.split("-")[-1] if "-" in entity_id else ""
        if not videoId:
            # fallback if they change it
            on_tap = renderer.get("onTap", {}).get("innertubeCommand", {}).get("commandMetadata", {}).get("webCommandMetadata", {}).get("url", "")
            if "/shorts/" in on_tap:
                videoId = on_tap.split("/shorts/")[1]
                
        if not videoId: return None
        
        # Title & Views
        meta = renderer.get("overlayMetadata", {})
        title = meta.get("primaryText", {}).get("content", "")
        view_text = meta.get("secondaryText", {}).get("content", "")
        
        # Thumbnail
        thumbnails = renderer.get("thumbnailViewModel", {}).get("thumbnailViewModel", {}).get("image", {}).get("sources", [])
        if not thumbnails:
            thumbnails = renderer.get("thumbnailViewModel", {}).get("image", {}).get("sources", [])
        thumb_url = thumbnails[-1].get("url", "") if thumbnails else ""
        
        return {
            "title": title,
            "url": f"https://www.youtube.com/shorts/{videoId}",
            "thumb": thumb_url,
            "views": view_text,
            "time": ""
        }
    except Exception:
        return None

async def extract_ytInitialData(page, url):
    print(f"Navigating to {url}...")
    await page.goto(url)
    
    # Try to dismiss consent popup if it exists
    try:
        reject_btn = page.locator("button:has-text('Reject all')").first
        await reject_btn.click(timeout=2000)
    except:
        pass
        
    try:
        await page.wait_for_function("typeof ytInitialData !== 'undefined'", timeout=10000)
        data = await page.evaluate("ytInitialData")
        return data
    except Exception as e:
        print(f"Failed to extract ytInitialData from {url}: {e}")
        return None

def generate_html_report(channel_name, videos, shorts, screenshot_filename):
    def make_cards(items):
        cards_html = ""
        for v in items:
            thumb_img = f'<img src="{v["thumb"]}" alt="Thumbnail" loading="lazy" />' if v["thumb"] else '<div class="no-img">🎥</div>'
            meta_str = v['views']
            if v['time']: meta_str += f" • {v['time']}"
            
            cards_html += f"""
            <div class="card">
                <div class="img-wrap">
                    <a href="{v['url']}" target="_blank">{thumb_img}</a>
                </div>
                <div class="body">
                    <div class="title"><a href="{v['url']}" target="_blank">{v['title']}</a></div>
                    <div class="meta">{meta_str}</div>
                </div>
            </div>
            """
        return cards_html

    date_str = datetime.now().strftime("%B %d, %Y")
    
    screenshot_html = ""
    if screenshot_filename:
        screenshot_html = f"""
        <div class="screenshot-wrap">
            <h2>Landing Page</h2>
            <img src="{screenshot_filename}" alt="Landing Page Screenshot" style="width: 100%; border-radius: 8px; border: 1px solid #333;" />
        </div>
        """
        
    videos_html = ""
    if videos:
        videos_html = f'<h2>Videos</h2><div class="grid">{make_cards(videos)}</div>'
        
    shorts_html = ""
    if shorts:
        shorts_html = f'<h2 style="margin-top: 40px;">Shorts</h2><div class="grid">{make_cards(shorts)}</div>'
    
    html = f"""<!DOCTYPE html><html lang="en">
    <head>
        <meta charset="UTF-8"/>
        <title>{channel_name} - YouTube Report</title>
        <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap" rel="stylesheet"/>
        <style>
            * {{ box-sizing: border-box; margin: 0; padding: 0; }}
            body {{ background: #0f0f0f; font-family: 'Roboto', sans-serif; padding: 40px 24px; color: #f1f1f1; }}
            .header {{ max-width: 1100px; margin: 0 auto 32px; padding-bottom: 20px; border-bottom: 2px solid #272727; }}
            .header h1 {{ font-size: 24px; font-weight: 700; }}
            .header p {{ font-size: 14px; color: #aaaaaa; margin-top: 4px; }}
            .screenshot-wrap {{ max-width: 1100px; margin: 0 auto 40px; }}
            h2 {{ max-width: 1100px; margin: 0 auto 16px; font-size: 20px; font-weight: 600; }}
            .grid {{ max-width: 1100px; margin: 0 auto; display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }}
            .card {{ background: #0f0f0f; border-radius: 8px; overflow: hidden; }}
            .img-wrap {{ width: 100%; aspect-ratio: 16/9; background: #272727; border-radius: 8px; overflow: hidden; }}
            .img-wrap img {{ width: 100%; height: 100%; object-fit: cover; transition: transform 0.2s; }}
            .img-wrap:hover img {{ transform: scale(1.05); }}
            .no-img {{ width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; font-size: 40px; color: #555; }}
            .body {{ padding: 12px 0; }}
            .title {{ font-size: 16px; font-weight: 500; line-height: 1.4; margin-bottom: 6px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }}
            .title a {{ color: #f1f1f1; text-decoration: none; }}
            .meta {{ font-size: 14px; color: #aaaaaa; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>{channel_name}</h1>
            <p>Generated {date_str} · {len(videos)} videos · {len(shorts)} shorts</p>
        </div>
        {screenshot_html}
        {videos_html}
        {shorts_html}
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
        
        for target in targets:
            base_url = target if target.startswith("http") else f"https://www.youtube.com/{target}"
            base_url = base_url.rstrip("/")
            
            channel_name = [part for part in base_url.split("/") if part and "@" in part]
            channel_name = channel_name[-1] if channel_name else "YouTube_Channel"
            
            # 1. Landing Page Screenshot
            print(f"\n--- Processing {channel_name} ---")
            print(f"Loading landing page: {base_url}")
            await page.goto(base_url)
            await asyncio.sleep(2) # let images load
            screenshot_filename = f"{channel_name}_landing.png"
            screenshot_path = os.path.join(data_dir, screenshot_filename)
            await page.screenshot(path=screenshot_path)
            print(f"Saved screenshot to {screenshot_path}")
            
            # 2. Extract Videos
            videos_url = base_url + "/videos"
            videos_data = await extract_ytInitialData(page, videos_url)
            parsed_videos = []
            if videos_data:
                renderers = list(find_keys(videos_data, "lockupViewModel"))
                for r in renderers:
                    v = parse_lockup_view_model(r, is_short=False)
                    if v and v not in parsed_videos:
                        parsed_videos.append(v)
                parsed_videos = parsed_videos[:limit]
            print(f"Extracted {len(parsed_videos)} videos.")
            
            # 3. Extract Shorts
            shorts_url = base_url + "/shorts"
            shorts_data = await extract_ytInitialData(page, shorts_url)
            parsed_shorts = []
            if shorts_data:
                # new structure
                renderers = list(find_keys(shorts_data, "shortsLockupViewModel"))
                for r in renderers:
                    s = parse_shorts_lockup_view_model(r)
                    if s and s not in parsed_shorts:
                        parsed_shorts.append(s)
                # old structure fallback
                if not parsed_shorts:
                    renderers = list(find_keys(shorts_data, "lockupViewModel"))
                    for r in renderers:
                        s = parse_lockup_view_model(r, is_short=True)
                        if s and s not in parsed_shorts:
                            parsed_shorts.append(s)
                parsed_shorts = parsed_shorts[:limit]
            print(f"Extracted {len(parsed_shorts)} shorts.")
            
            if not parsed_videos and not parsed_shorts:
                print(f"❌ No content found for {base_url}.")
                continue
                
            # 4. Generate Report
            html_content = generate_html_report(channel_name, parsed_videos, parsed_shorts, screenshot_filename)
            
            report_filename = f"{channel_name}_youtube.html"
            report_filepath = os.path.join(data_dir, report_filename)
            
            with open(report_filepath, "w", encoding="utf-8") as f:
                f.write(html_content)
                
            file_uri = f"file:///{os.path.abspath(report_filepath).replace(os.sep, '/')}"
            print(f"✅ Python successfully saved the report to: {report_filepath}")
            print(f"🔗 You can open it in your browser using this link: {file_uri}")
                
        await browser.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python youtube_agent.py <channel_url_or_handle1> ...")
        targets = ["@puma"] # default for test
        print("No targets provided, defaulting to @puma")
    else:
        targets = sys.argv[1:]
        
    print(f"Starting YouTube JSON scraper for {len(targets)} targets.")
    asyncio.run(run_report(targets, limit=20))
