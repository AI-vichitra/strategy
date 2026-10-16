import asyncio
import os
from datetime import datetime, timedelta
from jose import jwt
from playwright.async_api import async_playwright

SECRET_KEY = "supersecret"
ALGORITHM = "HS256"
USER_EMAIL = "apoorv@cogculture.agency"
BRAND_ID = "e09f39e4-dda0-4490-8f2b-42d643f27705" # PEPSICO Brand ID

def get_token():
    to_encode = {"sub": USER_EMAIL}
    expire = datetime.utcnow() + timedelta(days=7)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

ARTIFACT_DIR = r"C:\Users\Cog\.gemini\antigravity-ide\brain\85140e42-a63d-4f15-8890-4c23f9c23760"
SCREENSHOT_DIR = os.path.join(ARTIFACT_DIR, "pepsico_screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

token = get_token()

async def run_pepsico_capture():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        
        # Inject access_token and brand_config_id automatically on every page load
        await context.add_init_script(f"""
            localStorage.setItem('access_token', '{token}');
            localStorage.setItem('brand_config_id', '{BRAND_ID}');
        """)

        page = await context.new_page()

        # 1. PepsiCo Main Builder Studio View
        print("--- 1. Capturing PepsiCo Builder Studio Main View ---")
        await page.goto("http://localhost:3000/build", wait_until="networkidle")
        await page.wait_for_timeout(3500)
        await page.screenshot(path=os.path.join(SCREENSHOT_DIR, "01_pepsico_builder_main.png"), full_page=False)

        # 2. Workflow View
        print("--- 2. Capturing PepsiCo Workflow Studio ---")
        try:
            await page.click("text='Workflow'")
            await page.wait_for_timeout(1500)
            await page.screenshot(path=os.path.join(SCREENSHOT_DIR, "02_pepsico_workflow_view.png"), full_page=False)
        except Exception as e:
            print("Workflow click info:", e)

        # 3. Connectors View
        print("--- 3. Capturing PepsiCo Connector View ---")
        try:
            await page.click("text='Connector'")
            await page.wait_for_timeout(1500)
            await page.screenshot(path=os.path.join(SCREENSHOT_DIR, "03_pepsico_connector_view.png"), full_page=False)
        except Exception as e:
            print("Connector click info:", e)

        # 4. Files Generated View
        print("--- 4. Capturing PepsiCo Files Generated View ---")
        try:
            await page.click("text='Files Generated'")
            await page.wait_for_timeout(1500)
            await page.screenshot(path=os.path.join(SCREENSHOT_DIR, "04_pepsico_files_view.png"), full_page=False)
        except Exception as e:
            print("Files click info:", e)

        # 5. Agents View
        print("--- 5. Capturing PepsiCo Agents View ---")
        try:
            await page.click("text='Agents'")
            await page.wait_for_timeout(1500)
            await page.screenshot(path=os.path.join(SCREENSHOT_DIR, "05_pepsico_agents_view.png"), full_page=False)
        except Exception as e:
            print("Agents click info:", e)

        # 6. Projects View
        print("--- 6. Capturing PepsiCo Projects View ---")
        try:
            await page.click("text='Projects'")
            await page.wait_for_timeout(1500)
            await page.screenshot(path=os.path.join(SCREENSHOT_DIR, "06_pepsico_projects_view.png"), full_page=False)
        except Exception as e:
            print("Projects click info:", e)

        # 7. Competitive Analysis View
        print("--- 7. Capturing PepsiCo Competitive Analysis View ---")
        await page.goto("http://localhost:3000/competitive-analysis", wait_until="networkidle")
        await page.wait_for_timeout(2000)
        await page.screenshot(path=os.path.join(SCREENSHOT_DIR, "07_pepsico_competitive_analysis.png"), full_page=False)

        # 8. Brand Setup View
        print("--- 8. Capturing PepsiCo Brand Setup View ---")
        await page.goto("http://localhost:3000/brand-setup", wait_until="networkidle")
        await page.wait_for_timeout(2000)
        await page.screenshot(path=os.path.join(SCREENSHOT_DIR, "08_pepsico_brand_setup.png"), full_page=False)

        await browser.close()
        print("PepsiCo UI test capture completed successfully!")

if __name__ == "__main__":
    asyncio.run(run_pepsico_capture())
