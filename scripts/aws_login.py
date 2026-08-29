"""
AWS Remote Login Script

Run this on your AWS server to start a browser with Remote Debugging enabled.
Then, on your local machine, you can connect to it and solve the CAPTCHA.
"""

import asyncio
from playwright.async_api import async_playwright
from pathlib import Path
import json
import base64

async def main():
    print("="*60)
    print("AWS Remote Debugging Login")
    print("="*60)
    print("\nStarting Chrome with remote debugging on port 9222...")
    
    async with async_playwright() as p:
        # Launch headed=False but with remote debugging enabled
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--remote-debugging-port=9222",
                "--remote-debugging-address=0.0.0.0"
            ]
        )
        context = await browser.new_context(
            viewport={"width": 1365, "height": 900},
            locale="en-US",
        )
        page = await context.new_page()
        await page.goto("https://www.linkedin.com/login")
        
        print("\n" + "*"*60)
        print("BROWSER IS RUNNING ON AWS!")
        print("To see the browser and solve the CAPTCHA, run this on your LOCAL machine's terminal:")
        print("\n    ssh -L 9222:localhost:9222 your-aws-user@your-aws-ip")
        print("\nThen, open Google Chrome on your LOCAL computer and go to:")
        print("\n    http://localhost:9222")
        print("*"*60)
        
        print("\nWaiting for you to log in (will wait up to 10 minutes)...")
        
        # Wait for the user to log in via remote debugging
        try:
            await page.wait_for_url("**/feed/**", timeout=600_000)
            print("\n[OK] Login detected! Capturing session...")
            await page.wait_for_timeout(3000) # Let cookies settle
        except Exception:
            print("\n[WARN] Did not detect feed. Capturing whatever state is there...")

        state = await context.storage_state()
        await browser.close()
        
    # Save the state
    json_str = json.dumps(state)
    b64 = base64.b64encode(json_str.encode("utf-8")).decode("utf-8")
    
    env_path = Path(".env")
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
        new_lines = [l for l in lines if not l.startswith("LINKEDIN_STORAGE_STATE_B64")]
        new_lines.append(f"LINKEDIN_STORAGE_STATE_B64={b64}")
        env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        print("\n[OK] Session saved directly to AWS .env!")
        print("You can now restart your AWS API server.")

if __name__ == "__main__":
    asyncio.run(main())
