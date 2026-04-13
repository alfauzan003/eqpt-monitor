"""Request timing and metrics middleware."""
from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from api.metrics import HTTP_REQUESTS_TOTAL, HTTP_REQUEST_DURATION


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip metrics endpoint itself to avoid recursion
        if request.url.path == "/metrics":
            return await call_next(request)

        method = request.method
        # Normalize path to avoid cardinality explosion
        path = request.url.path
        for segment in path.split("/"):
            if segment and not segment.startswith(("api", "ws", "equipment", "telemetry", "batches", "health", "metrics")):
                # Likely an ID segment — normalize
                path = path.replace(segment, "{id}", 1)
                break

        start = time.monotonic()
        response = await call_next(request)
        duration = time.monotonic() - start

        HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status=response.status_code).inc()
        HTTP_REQUEST_DURATION.labels(method=method, path=path).observe(duration)

        return response
