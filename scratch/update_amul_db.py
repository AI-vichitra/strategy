import asyncio
import re
import os
import base64
import uuid
from sqlalchemy import select
from backend.database import AsyncSessionLocal
from backend.models.brand import BrandConfig

PROJECT_NAME = "amul"
BRAND_CONFIG_ID = "faf42eba-5c68-44e2-ad13-c42a8e8a3fc2"
TARGETS = ["amul_india", "kwalitywallsicecreamshop_blr", "baskinrobbins"]

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # Strategy root
PROJECT_SCRAPPED_DIR = os.path.join(BASE_DIR, "docs", "project_scrapped", f"{PROJECT_NAME}_scrapped")
STATIC_DIR = os.path.join(BASE_DIR, "backend", "static", "images")
os.makedirs(STATIC_DIR, exist_ok=True)

def process_html_to_text(clean_name: str):
    report_path = os.path.join(PROJECT_SCRAPPED_DIR, f"{clean_name}_insta.html")
    results = [f"Report for {clean_name}:"]
    try:
        with open(report_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        cards = re.findall(r'<div class="card">(.*?)</div></div>', html_content, re.DOTALL)
        md_content = f"# Instagram Scraping Report for @{clean_name}\n\n"

        if cards:
            extracted_posts = []
            for idx, card in enumerate(cards[:15]):
                link_match = re.search(r'href="(https://instagram\.com/p/[^"]+)"', card)
                link = link_match.group(1) if link_match else "No URL"

                img_match = re.search(r'<img src="([^"]+)"', card)
                img_url = ""
                if img_match:
                    src = img_match.group(1)
                    if src.startswith("data:image/"):
                        try:
                            header, encoded = src.split(",", 1)
                            ext = header.split(";")[0].split("/")[1]
                            if ext == "jpeg": ext = "jpg"
                            img_data = base64.b64decode(encoded)
                            filename = f"post_{uuid.uuid4().hex[:8]}.{ext}"
                            file_path = os.path.join(STATIC_DIR, filename)
                            with open(file_path, "wb") as img_f:
                                img_f.write(img_data)
                            img_url = f"http://localhost:8000/static/images/{filename}"
                        except Exception as e:
                            print("Failed to save base64 image:", e)
                    else:
                        img_url = src

                text_content = re.sub(r'<[^>]+>', ' ', card)
                text_content = re.sub(r'\s+', ' ', text_content).strip()

                post_data = f"Post {idx+1}: {text_content} | URL: {link}"
                if img_url:
                    post_data += f" | ImageURL: {img_url}"
                extracted_posts.append(post_data)

                md_content += f"### Post {idx+1}\n"
                md_content += f"- **Caption/Text**: {text_content}\n"
                md_content += f"- **URL**: [{link}]({link})\n"
                if img_url:
                    md_content += f"- **Image**: ![]({img_url})\n"
                md_content += "\n"

            final_text = "\n".join(extracted_posts)
            results.append(final_text[:3000])
        else:
            html_clean = re.sub(r'<style[^>]*>[\s\S]*?</style>', ' ', html_content, flags=re.IGNORECASE)
            html_clean = re.sub(r'<script[^>]*>[\s\S]*?</script>', ' ', html_clean, flags=re.IGNORECASE)
            text_content = re.sub(r'<[^>]+>', ' ', html_clean)
            text_content = re.sub(r'\s+', ' ', text_content).strip()
            results.append(text_content[:2000])
            md_content += text_content

        md_report_path = os.path.join(PROJECT_SCRAPPED_DIR, f"{clean_name}_insta.md")
        with open(md_report_path, "w", encoding="utf-8") as md_f:
            md_f.write(md_content)
        print(f"[OK] Processed {clean_name}: {len(extracted_posts if cards else [])} posts, md saved.")
    except Exception as e:
        results.append(f"Could not read data: {e}")
        print(f"[ERROR] {clean_name}: {e}")
    return results

async def update_db():
    social_reports = []
    for target in TARGETS:
        reports = process_html_to_text(target)
        social_reports.extend(reports)

    social_metrics_text = "Social Scraped Data:\n" + "\n".join(social_reports)

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(BrandConfig).where(BrandConfig.id == BRAND_CONFIG_ID))
        brand_config = result.scalars().first()
        if brand_config:
            brand_config.social_metrics = social_metrics_text
            await session.commit()
            print(f"\n[DB] Updated AMUL social_metrics. Total length: {len(social_metrics_text)} chars")
        else:
            print(f"[DB] ERROR: BrandConfig {BRAND_CONFIG_ID} not found.")

if __name__ == "__main__":
    asyncio.run(update_db())
