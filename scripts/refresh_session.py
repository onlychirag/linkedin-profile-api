"""
Refresh LinkedIn session locally and push it to your remote deployment.

Usage:
  python scripts/refresh_session.py                          # just save locally
  python scripts/refresh_session.py https://your-aws-url.com # save + push to remote
  python scripts/refresh_session.py http://127.0.0.1:8000    # save + push to local server
"""

import asyncio
import base64
import json
import sys

import httpx


async def main():
    from playwright.async_api import async_playwright

    remote_url = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else None

    print("=" * 60)
    print("  LinkedIn Session Refresher")
    print("=" * 60)
    print()
    print("A Chromium window will open. Please:")
    print("  1. Log in to LinkedIn (solve any CAPTCHA)")
    print("  2. Wait until the feed loads")
    print("  3. Close the browser window when done")
    print()

    async with async_playwright() as p:
        proxy = None
        import os
        proxy_url = os.getenv("PROXY_URL")
        if proxy_url:
            print(f"Using proxy: {proxy_url}")
            proxy = {"server": proxy_url}

        browser = await p.chromium.launch(
            headless=False,
            proxy=proxy
        )
        context = await browser.new_context(
            viewport={"width": 1365, "height": 900},
            locale="en-US",
        )
        page = await context.new_page()
        await page.goto("https://www.linkedin.com/login")

        # Wait for the user to log in and close the browser
        try:
            await page.wait_for_url("**/feed/**", timeout=300_000)  # 5 min to log in
            print("[OK] Login detected! Capturing session...")
            await page.wait_for_timeout(3000)  # let cookies settle
        except Exception:
            print("[WARN] Feed page not detected. Capturing current state anyway...")

        state = await context.storage_state()
        await browser.close()

    # Encode
    json_str = json.dumps(state)
    b64 = base64.b64encode(json_str.encode("utf-8")).decode("utf-8")
    cookie_count = len(state.get("cookies", []))

    # Save locally
    from pathlib import Path
    state_path = Path(".auth/linkedin-state.json")
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json_str, encoding="utf-8")
    print(f"[OK] Saved {cookie_count} cookies to {state_path}")

    # Also update .env
    env_path = Path(".env")
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
        new_lines = [l for l in lines if not l.startswith("LINKEDIN_STORAGE_STATE_B64")]
        new_lines.append(f"LINKEDIN_STORAGE_STATE_B64={b64}")
        env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        print("[OK] Updated .env with new session")

    # Push to remote if URL provided
    if remote_url:
        print(f"\n-> Pushing session to {remote_url}...")
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{remote_url}/api/auth/session",
                    json={"storage_state_b64": b64},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    print(f"[OK] Remote updated: {data.get('message', 'OK')}")
                else:
                    print(f"[FAIL] Remote returned {resp.status_code}: {resp.text}")
        except Exception as exc:
            print(f"[FAIL] Could not reach remote: {exc}")

    print("\n[OK] Done! The scraper will use the new session on next request.")


if __name__ == "__main__":
    asyncio.run(main())
