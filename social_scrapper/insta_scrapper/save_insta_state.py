import os
import asyncio
from playwright.async_api import async_playwright

async def save_state():
    async with async_playwright() as p:
        # Launch browser visibly so the user can log in
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        print("Navigating to Instagram...")
        await page.goto("https://www.instagram.com/accounts/login/")
        
        print("\n*** ACTION REQUIRED ***")
        print("Please log in to your Instagram account in the browser window.")
        print("Once you are logged in and see your home feed/dashboard, return to this terminal and press ENTER to save your session...")
        
        # Wait for user to press enter in the console
        await asyncio.get_event_loop().run_in_executor(None, input)
        
        state_path = os.path.join(os.path.dirname(__file__), "insta_state.json")
        await context.storage_state(path=state_path)
        print(f"✅ Success! Session state saved to {state_path}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(save_state())
