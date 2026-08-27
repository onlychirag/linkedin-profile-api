"""
FastAPI Application Entry Point.

This is the main file that:
  - Creates the FastAPI app instance
  - Configures CORS middleware (allows all origins for demo purposes)
  - Adds request logging middleware
  - Registers the global exception handler
  - Mounts the profile router
  - Provides a health check endpoint at GET /
"""

from __future__ import annotations

import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routes.profile import router as profile_router

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ────────────────────────────────────────────
# Create the FastAPI application
# ────────────────────────────────────────────
app = FastAPI(
    title="LinkedIn Profile API",
    description=(
        "A reverse-engineered LinkedIn API that accepts a profile URL "
        "and returns structured JSON data including name, headline, "
        "experience, education, skills, and more."
    ),
    version="1.0.0",
    docs_url="/docs",       # Swagger UI
    redoc_url="/redoc",     # ReDoc
    openapi_url="/openapi.json",
)

# ────────────────────────────────────────────
# Middleware: CORS
# ────────────────────────────────────────────
# Allow all origins for this demo/challenge API.
# In production, restrict to specific domains.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ────────────────────────────────────────────
# Middleware: Request Logging
# ────────────────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log every request with method, path, status, and duration."""
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    logger.info(
        f"{request.method} {request.url.path} → {response.status_code} ({duration:.2f}s)"
    )
    return response


# ────────────────────────────────────────────
# Global Exception Handler
# ────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all handler to prevent raw stack traces from leaking to clients."""
    logger.exception(f"Unhandled exception on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "detail": str(exc),
        },
    )


# ────────────────────────────────────────────
# Mount Routers
# ────────────────────────────────────────────
app.include_router(profile_router)


# ────────────────────────────────────────────
# Health Check
# ────────────────────────────────────────────
@app.get("/", tags=["Health"])
async def health_check():
    """
    Simple health check endpoint.
    Returns 200 OK if the service is running.
    """
    return {
        "status": "ok",
        "service": "linkedin-profile-api",
        "version": "1.0.0",
        "docs": "/docs",
    }
