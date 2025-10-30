"""
Custom middleware for FastAPI application.

Includes:
- Request ID generation
- Request timing/logging
- Structured logging
"""

import logging
import time
import uuid
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

# Configure structured logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("hefesto.api")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Adds unique request ID to each request.

    Request ID is:
    - Generated as UUID4
    - Added to request state
    - Returned in X-Request-ID header
    """

    async def dispatch(self, request: Request, call_next: Callable):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id

        return response


class TimingMiddleware(BaseHTTPMiddleware):
    """
    Logs request duration.

    Measures time from request start to response completion.
    Logs: method, path, status_code, duration_ms
    """

    async def dispatch(self, request: Request, call_next: Callable):
        start_time = time.time()

        response = await call_next(request)

        duration_ms = (time.time() - start_time) * 1000

        logger.info(
            f"{request.method} {request.url.path} - "
            f"Status: {response.status_code} - "
            f"Duration: {duration_ms:.2f}ms"
        )

        # Add timing header
        response.headers["X-Process-Time"] = f"{duration_ms:.2f}ms"

        return response


def add_middlewares(app):
    """
    Add all custom middleware to FastAPI app.

    Call this in main.py after app initialization.

    Args:
        app: FastAPI application instance
    """
    app.add_middleware(TimingMiddleware)
    app.add_middleware(RequestIDMiddleware)
