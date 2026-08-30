import time
import json
import base64
import requests
import sys
from playwright.sync_api import sync_playwright

API_URL = "https://ontross.omniswitch.dev"

def main():
    print("Launching your real Google Chrome in stealth mode...")
    with sync_playwright() as p:
        # Use real Google Chrome to avoid Playwright fingerprinting
        browser = p.chromium.launch(
            channel="chrome",
            headless=False,
            proxy={"server": "socks5://127.0.0.1:9090"}
        )
        context = browser.new_context(
            viewport={"width": 1366, "height": 768}
        )
        page = context.new_page()
        page.goto("https://www.linkedin.com/login")
        
        print("\nChrome is open on your screen! Please log in and solve the CAPTCHA.")
        print("Waiting for you to reach the feed...")
        
        # Wait until the user successfully logs in
        while True:
            try:
                if page.locator(".feed-identity-module").count() > 0 or "feed" in page.url:
                    break
                time.sleep(2)
            except Exception:
                time.sleep(2)
                
        print("\nLogin detected! Extracting your bulletproof session...")
        state = context.storage_state()
        browser.close()
        
        b64_state = base64.b64encode(json.dumps(state).encode("utf-8")).decode("utf-8")
        
        print("Pushing the pristine session to your AWS server...")
        try:
            resp = requests.post(
                f"{API_URL}/api/auth/session",
                json={"storage_state_b64": b64_state},
                timeout=10
            )
            resp.raise_for_status()
            print("SUCCESS! The server has received the new session and is ready to scrape.")
        except Exception as e:
            print(f"Failed to push session: {e}")

if __name__ == "__main__":
    main()
