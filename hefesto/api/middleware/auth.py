"""
API Key authentication middleware for Hefesto API.

If HEFESTO_API_KEY is set, requires X-API-Key header on all
requests except health/ping endpoints.

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

import logging
from typing import Callable, Set

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("hefesto.api.auth")

# Paths that bypass auth (no trailing slash)
BYPASS_PATHS: Set[str] = {"/health", "/ping", "/"}


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Require X-API-Key header when HEFESTO_API_KEY is configured."""

    def __init__(self, app, api_key: str = ""):
        super().__init__(app)
        self.api_key = api_key

    async def dispatch(self, request: Request, call_next: Callable):
        # Skip if no key configured
        if not self.api_key:
            return await call_next(request)

        # Bypass health / ping / root
        path = request.url.path.rstrip("/") or "/"
        if path in BYPASS_PATHS:
            return await call_next(request)

        # Check header
        provided = request.headers.get("X-API-Key", "")
        if provided != self.api_key:
            logger.warning(
                "Unauthorized request to %s from %s",
                request.url.path,
                request.client.host if request.client else "unknown",
            )
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized"},
            )

        return await call_next(request)
