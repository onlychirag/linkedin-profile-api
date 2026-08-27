"""
Vercel Serverless Function Entry Point.

Vercel expects a Python file in the /api directory that exports a
WSGI/ASGI-compatible application. We import our FastAPI app and
expose it as 'app' — Vercel's Python runtime handles the rest.

NOTE: Playwright (browser fallback) will NOT work on Vercel because
serverless functions have a 50MB deployment limit and no access to
system-level browser binaries. The Voyager API strategy (primary)
works perfectly on Vercel since it only uses httpx (pure HTTP requests).
If the Voyager strategy fails, the browser fallback will gracefully
error out and the API will return a 500 with an explanatory message.
"""

from app.main import app  # noqa: F401

# Vercel's @vercel/python builder automatically detects this `app` object
# and wraps it with Mangum (or its internal ASGI adapter) to serve it
# as a serverless function.
