import logging
import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = logging.getLogger("app.http")

_SKIP_PREFIXES = (
    "/css/",
    "/js/",
    "/api/uploads/",
    "/favicon",
)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path
        if path != "/api/health" and not any(path.startswith(p) for p in _SKIP_PREFIXES):
            if not (path.endswith(".js") or path.endswith(".css") or path.endswith(".html")):
                return await self._log_request(request, call_next)
        return await call_next(request)

    async def _log_request(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start = time.perf_counter()
        user_id = request.headers.get("X-Dev-User-Id", "-")

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.exception(
                "HTTP %s %s | user=%s | failed in %.1fms",
                request.method,
                request.url.path,
                user_id,
                duration_ms,
            )
            raise

        duration_ms = (time.perf_counter() - start) * 1000
        status = response.status_code
        message = (
            f"HTTP {request.method} {request.url.path} -> {status} "
            f"| user={user_id} | {duration_ms:.1f}ms"
        )

        if status >= 500:
            logger.error(message)
        elif status >= 400:
            logger.warning(message)
        else:
            logger.info(message)

        return response
