from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
from pathlib import Path
import shutil

from playwright.async_api import async_playwright


AUTH_URL_MARKERS = ("/login", "/checkpoint", "uas/login", "authwall")
PROFILE_READY_MARKER = ".codex-linkedin-ready"
SIGNED_IN_MARKERS = (
    "Start a post",
    "My Network",
    "Messaging",
    "Notifications",
    "View my profile",
)


def is_auth_wall(url: str) -> bool:
    lowered = url.lower()
    return any(marker in lowered for marker in AUTH_URL_MARKERS)


async def has_linkedin_session(context) -> bool:
    cookies = await context.cookies("https://www.linkedin.com")
    return any(cookie.get("name") == "li_at" for cookie in cookies)


async def page_looks_signed_in(page, context) -> bool:
    if not await has_linkedin_session(context):
        return False
    if is_auth_wall(page.url):
        return False
    try:
        text = await page.locator("body").inner_text(timeout=3000)
    except Exception:
        text = ""
    if "Sign in" in text and "Join now" in text:
        return False
    return any(marker in text for marker in SIGNED_IN_MARKERS)


async def wait_for_login(page, context, timeout_seconds: int) -> None:
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while asyncio.get_running_loop().time() < deadline:
        if await page_looks_signed_in(page, context):
            return
        await page.wait_for_timeout(2000)
    raise TimeoutError(
        "Timed out waiting for LinkedIn login. Re-run the script and finish login, MFA, "
        "or checkpoint verification in the browser window."
    )


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a Playwright storage state by logging in to LinkedIn manually."
    )
    parser.add_argument(
        "--output",
        default=".auth/linkedin-state.json",
        help="Where to write the portable storage-state JSON.",
    )
    parser.add_argument(
        "--profile-dir",
        default=".auth/linkedin-browser-profile",
        help="Persistent browser profile directory. This is the preferred local method.",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Move the existing profile aside and create a new one at --profile-dir.",
    )
    parser.add_argument("--email", default=None, help="Optional email to prefill.")
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=600,
        help="How long to wait for login completion before failing.",
    )
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    profile_dir = Path(args.profile_dir)
    if args.fresh and profile_dir.exists():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = profile_dir.with_name(f"{profile_dir.name}.backup-{stamp}")
        shutil.move(str(profile_dir), str(backup))
        print(f"Moved existing browser profile to {backup}")
    ready_marker = profile_dir / PROFILE_READY_MARKER
    if ready_marker.exists():
        ready_marker.unlink()
    if output.exists():
        output.unlink()
    profile_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as playwright:
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            viewport={"width": 1365, "height": 900},
            locale="en-US",
        )
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
        if args.email:
            await page.fill("input[name='session_key']", args.email)

        print("Complete LinkedIn login in the opened browser window.")
        print("If LinkedIn asks for MFA or checkpoint verification, finish it there.")
        print("This script will save the session automatically after login succeeds.")
        await wait_for_login(page, context, args.timeout_seconds)

        await context.storage_state(path=str(output))
        (profile_dir / PROFILE_READY_MARKER).write_text("ok\n", encoding="utf-8")
        await context.close()
        print(f"Saved persistent browser profile to {profile_dir}")
        print(f"Saved LinkedIn browser session to {output}")


if __name__ == "__main__":
    asyncio.run(main())
