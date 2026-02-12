"""
Hefesto API - Main FastAPI Application

This is the entry point for the REST API server.
Accessed via: hefesto serve

Provides:
- Health check endpoints
- Code analysis API
- Findings management
- Iris integration endpoints
- Metrics & analytics
"""

from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from hefesto.__version__ import __version__
from hefesto.api.middleware import add_middlewares
from hefesto.api.routers import analysis, findings, health
from hefesto.config.settings import Settings, get_settings


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    """
    Create and configure the FastAPI application.

    Args:
        settings: Optional Settings override (for testing).
                  Defaults to get_settings() singleton.

    Returns:
        Configured FastAPI application instance.
    """
    if settings is None:
        settings = get_settings()

    # --- Docs toggle ---
    docs_url = "/docs" if settings.expose_docs else None
    redoc_url = "/redoc" if settings.expose_docs else None
    openapi_url = "/openapi.json" if settings.expose_docs else None

    application = FastAPI(
        title="Hefesto API",
        description="AI-powered code quality analysis and monitoring",
        version=__version__,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        contact={
            "name": "Hefesto Team",
            "email": "support@narapallc.com",
            "url": "https://github.com/artvepa80/Agents-Hefesto",
        },
        license_info={
            "name": "Dual License",
            "url": ("https://github.com/artvepa80/Agents-Hefesto" "/blob/main/LICENSE"),
        },
    )

    # --- CORS enforcement (Hardened) ---
    origins = settings.parsed_cors_origins
    allow_creds = settings.cors_allow_credentials

    # Block dangerous wildcard + credentials combo (Fail fast)
    if allow_creds and "*" in origins:
        raise RuntimeError(
            "Security Error: Cannot use '*' in CORS origins with allow_credentials=True. "
            "Set HEFESTO_CORS_ORIGINS to specific domains."
        )

    if origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=allow_creds,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # --- Custom middleware (timing, request ID, auth, rate limit, sandbox) ---
    add_middlewares(application, settings)

    # --- Register routers ---
    application.include_router(health.router)
    application.include_router(analysis.router)
    application.include_router(findings.router)

    # --- Root endpoint ---
    @application.get(
        "/",
        summary="API Root",
        description=("Welcome endpoint with API information and documentation links"),
    )
    async def root():
        """API root endpoint."""
        doc_links = {}
        if settings.expose_docs:
            doc_links = {
                "swagger": "/docs",
                "redoc": "/redoc",
                "openapi_json": "/openapi.json",
            }

        return {
            "message": "Welcome to Hefesto API",
            "version": __version__,
            "documentation": (
                doc_links if doc_links else {"note": "Docs disabled. Set HEFESTO_EXPOSE_DOCS=true"}
            ),
            "endpoints": {
                "health": "/health",
                "status": "/api/v1/status",
            },
        }

    # --- Lifecycle events ---
    @application.on_event("startup")
    async def startup_event():
        """Run on application startup."""
        print(f"🚀 Hefesto API v{__version__} starting...")
        bind = f"{settings.api_host}:{settings.api_port}"
        print(f"🔒 Binding to {bind}")

        if settings.expose_docs:
            print(f"📚 Documentation: http://{bind}/docs")
        else:
            print("📚 Documentation disabled (secure default)")

        print(f"🔍 Health check: http://{bind}/health")

    @application.on_event("shutdown")
    async def shutdown_event():
        """Run on application shutdown."""
        print(f"👋 Hefesto API v{__version__} shutting down...")

    return application


# Global app instance for uvicorn/gunicorn
app = create_app()
