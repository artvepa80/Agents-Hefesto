"""
Rate limiting middleware for Hefesto API.

Uses a sliding-window counter per client key (API key or IP).
Only active when HEFESTO_API_RATE_LIMIT_PER_MINUTE > 0.

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

import logging
import time
from collections import defaultdict
from typing import Callable, Dict, List

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("hefesto.api.ratelimit")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter per client key."""

    def __init__(self, app, max_requests: int = 0):
        super().__init__(app)
        self.max_requests = max_requests
        # key -> list of timestamps
        self._windows: Dict[str, List[float]] = defaultdict(list)
        self._last_cleanup = time.monotonic()
        self._cleanup_interval = 60.0  # seconds

    def _client_key(self, request: Request) -> str:
        """Determine client key: prefer API key, fall back to IP."""
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return f"key:{api_key}"
        host = request.client.host if request.client else "unknown"
        return f"ip:{host}"

    def _cleanup_stale(self, now: float) -> None:
        """Remove entries older than 60s to prevent memory leak."""
        if now - self._last_cleanup < self._cleanup_interval:
            return
        cutoff = now - 60.0
        stale_keys = [k for k, ts in self._windows.items() if not ts or ts[-1] < cutoff]
        for k in stale_keys:
            del self._windows[k]
        self._last_cleanup = now

    async def dispatch(self, request: Request, call_next: Callable):
        # Disabled if max_requests <= 0
        if self.max_requests <= 0:
            return await call_next(request)

        now = time.monotonic()
        self._cleanup_stale(now)

        key = self._client_key(request)
        window = self._windows[key]

        # Trim timestamps older than 60s
        cutoff = now - 60.0
        while window and window[0] < cutoff:
            window.pop(0)

        if len(window) >= self.max_requests:
            logger.warning(
                "Rate limit exceeded for %s (%d/%d per min)",
                key,
                len(window),
                self.max_requests,
            )
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
            )

        window.append(now)
        return await call_next(request)
