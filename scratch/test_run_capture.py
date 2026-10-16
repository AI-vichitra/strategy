import asyncio
import os
from datetime import datetime, timedelta
from jose import jwt
from playwright.async_api import async_playwright

SECRET_KEY = "supersecret"
ALGORITHM = "HS256"
BRAND_ID = "b55da406-9957-4929-b937-be566c9bbe60"

def get_demo_token():
    to_encode = {"sub": "demo@stratai.com"}
    expire = datetime.utcnow() + timedelta(days=7)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

ARTIFACT_DIR = r"C:\Users\Cog\.gemini\antigravity-ide\brain\85140e42-a63d-4f15-8890-4c23f9c23760"
SCREENSHOT_DIR = os.path.join(ARTIFACT_DIR, "ui_screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

token = get_demo_token()

async def run_test_run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        
        # Inject access_token and brand_config_id automatically on every page load
        await context.add_init_script(f"""
            localStorage.setItem('access_token', '{token}');
            localStorage.setItem('brand_config_id', '{BRAND_ID}');
        """)

        page = await context.new_page()

        # 1. Landing Page
        print("--- 1. Capturing Landing Page ---")
        # Clear token for landing page view
        await page.goto("http://localhost:3000/", wait_until="networkidle")
        await page.wait_for_timeout(1000)
        await page.screenshot(path=os.path.join(SCREENSHOT_DIR, "01_landing_page_hero.png"), full_page=False)
        await page.screenshot(path=os.path.join(SCREENSHOT_DIR, "01_landing_page_full.png"), full_page=True)

        # 2. Auth Page
        print("--- 2. Capturing Auth Page ---")
        await page.goto("http://localhost:3000/auth", wait_until="networkidle")
        await page.wait_for_timeout(1000)
        await page.screenshot(path=os.path.join(SCREENSHOT_DIR, "02_auth_page.png"), full_page=False)

        # Re-set tokens after Auth page
        await page.evaluate(f"""
            localStorage.setItem('access_token', '{token}');
            localStorage.setItem('brand_config_id', '{BRAND_ID}');
        """)

        # 3. Strategy Setup Page
        print("--- 3. Capturing Strategy Setup Page ---")
        await page.goto("http://localhost:3000/strategy-setup", wait_until="networkidle")
        await page.wait_for_timeout(2000)
        await page.screenshot(path=os.path.join(SCREENSHOT_DIR, "03_strategy_setup.png"), full_page=False)

        # 4. Brand Setup Page
        print("--- 4. Capturing Brand Setup Page ---")
        await page.goto("http://localhost:3000/brand-setup?new=true", wait_until="networkidle")
        await page.wait_for_timeout(2000)
        await page.screenshot(path=os.path.join(SCREENSHOT_DIR, "04_brand_setup.png"), full_page=False)

        # Fill brand details
        try:
            brand_input = page.locator("input[placeholder='e.g. StratAI']").first
            if await brand_input.is_visible():
                await brand_input.fill("Apex Strategy Corp")
                await page.fill("input[placeholder='https://www.yourbrand.com/']", "https://apexstrategy.com")
                await page.select_option("select", "Technology & Software")
                await page.screenshot(path=os.path.join(SCREENSHOT_DIR, "04_brand_setup_filled.png"), full_page=False)
        except Exception as e:
            print("Brand setup fill exception:", e)

        # 5. Builder Studio Page - Main Studio & Components
        print("--- 5. Capturing Builder Studio ---")
        await page.goto("http://localhost:3000/build", wait_until="networkidle")
        await page.wait_for_timeout(3000)
        await page.screenshot(path=os.path.join(SCREENSHOT_DIR, "05_builder_studio_main.png"), full_page=False)

        # Click side buttons to capture sub-views
        for label, file_suffix in [("Workflow", "workflow"), ("Connectors", "connectors"), ("Files", "files"), ("Projects", "projects"), ("Agents", "agents")]:
            try:
                el = page.locator(f"text='{label}'").first
                if await el.is_visible():
                    await el.click()
                    await page.wait_for_timeout(1000)
                    await page.screenshot(path=os.path.join(SCREENSHOT_DIR, f"05_builder_studio_{file_suffix}.png"), full_page=False)
            except Exception as e:
                print(f"Subview {label} click info:", e)

        # 6. Competitive Analysis Page
        print("--- 6. Capturing Competitive Analysis ---")
        await page.goto("http://localhost:3000/competitive-analysis", wait_until="networkidle")
        await page.wait_for_timeout(2000)
        await page.screenshot(path=os.path.join(SCREENSHOT_DIR, "06_competitive_analysis.png"), full_page=False)

        await browser.close()
        print("Test run finished successfully!")

if __name__ == "__main__":
    asyncio.run(run_test_run())
