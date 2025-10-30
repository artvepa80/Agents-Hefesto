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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from hefesto.__version__ import __version__
from hefesto.api.middleware import add_middlewares
from hefesto.api.routers import analysis, findings, health

# Initialize FastAPI app
app = FastAPI(
    title="Hefesto API",
    description="AI-powered code quality analysis and monitoring",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    contact={
        "name": "Hefesto Team",
        "email": "sales@narapallc.com",
        "url": "https://github.com/artvepa80/Agents-Hefesto",
    },
    license_info={
        "name": "Dual License",
        "url": "https://github.com/artvepa80/Agents-Hefesto/blob/main/LICENSE",
    },
)

# CORS middleware - configure per environment
# TODO: Restrict origins in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Configure via environment variable
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add custom middleware (timing, request ID, logging)
add_middlewares(app)

# Register routers
app.include_router(health.router)

# Phase 2: Analysis endpoints
app.include_router(analysis.router)

# Phase 3: Findings endpoints
app.include_router(findings.router)
# TODO Phase 4: app.include_router(iris.router, prefix="/api/v1/iris")
# TODO Phase 5: app.include_router(metrics.router, prefix="/api/v1/metrics")
# TODO Phase 6: app.include_router(config.router, prefix="/api/v1")


@app.get(
    "/",
    summary="API Root",
    description="Welcome endpoint with API information and documentation links",
)
async def root():
    """
    API root endpoint.

    Returns basic API information and links to documentation.
    """
    return {
        "message": "Welcome to Hefesto API",
        "version": __version__,
        "documentation": {"swagger": "/docs", "redoc": "/redoc", "openapi_json": "/openapi.json"},
        "endpoints": {"health": "/health", "status": "/api/v1/status"},
    }


# Application startup event
@app.on_event("startup")
async def startup_event():
    """
    Run on application startup.

    Future use:
    - Initialize database connections
    - Warm up ML models
    - Check external service availability
    """
    print(f"🚀 Hefesto API v{__version__} starting...")
    print("📚 Documentation: http://localhost:8000/docs")
    print("🔍 Health check: http://localhost:8000/health")


# Application shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """
    Run on application shutdown.

    Future use:
    - Close database connections
    - Flush logs
    - Cleanup resources
    """
    print(f"👋 Hefesto API v{__version__} shutting down...")
