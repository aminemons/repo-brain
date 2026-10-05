"""API access policy and bounded rate limits; token values never enter audit logs."""

import hashlib
import hmac
import logging
import time
from collections import OrderedDict

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from backend.app.config import Settings

audit = logging.getLogger("project_brain.audit")


class ProjectSecurityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, settings: Settings) -> None:
        super().__init__(app)
        self.settings = settings
        self.windows: OrderedDict[str, tuple[float, int]] = OrderedDict()

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        started = time.monotonic()
        path = request.url.path
        role = "local"
        if path.startswith("/api/") and path != "/api/health" and request.method != "OPTIONS":
            role = self._role(request.headers.get("authorization", ""))
            if role == "denied":
                return self._secure(JSONResponse(
                    {"detail": "API access token required. Enter it in Settings."},
                    status_code=401, headers={"WWW-Authenticate": "Bearer"},
                ))
            parts = path.strip("/").split("/")
            read_query = (
                request.method == "POST" and len(parts) >= 4
                and parts[:2] == ["api", "repos"]
                and "/".join(parts[3:]) in {
                    "ask", "graph/explore", "graph/affected", "graphrag/retrieve",
                }
            )
            if role == "viewer" and request.method not in {"GET", "HEAD"} and not read_query:
                return self._secure(JSONResponse(
                    {"detail": "This token has read-only access."}, status_code=403,
                ))
            if not self._rate_allowed(request):
                return self._secure(JSONResponse(
                    {"detail": "API request limit reached. Retry in one minute."},
                    status_code=429, headers={"Retry-After": "60"},
                ))
        request.state.project_role = role
        try:
            response = await call_next(request)
        except ValueError as exc:
            response = JSONResponse({"detail": str(exc)}, status_code=400)
        if path == "/api/bots" or path.startswith("/api/bots/"):
            response.headers["Cache-Control"] = "no-store"
        if path.startswith("/api/") and path != "/api/health":
            # Do not log queries, credentials, excerpts, or user-supplied paths.
            endpoint = request.scope.get("route")
            route = getattr(endpoint, "path", "/api/<unmatched>")
            audit.info("method=%s route=%s role=%s status=%d elapsed_ms=%d",
                       request.method, route, role, response.status_code,
                       round((time.monotonic() - started) * 1000))
        return self._secure(response)

    def _role(self, authorization: str) -> str:
        owner = self.settings.auth_token
        viewer = self.settings.viewer_token
        if not owner and not viewer:
            return "local"
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return "denied"
        if owner and hmac.compare_digest(token.encode(), owner.encode()):
            return "owner"
        if viewer and hmac.compare_digest(token.encode(), viewer.encode()):
            return "viewer"
        return "denied"

    def _rate_allowed(self, request: Request) -> bool:
        peer = request.client.host if request.client else "unknown"
        digest = hashlib.sha256(request.headers.get("authorization", "").encode()).hexdigest()
        key = peer + digest
        now = time.monotonic()
        window, count = self.windows.pop(key, (now, 0))
        if now - window >= 60:
            window, count = now, 0
        self.windows[key] = (window, count + 1)
        while len(self.windows) > 4096:
            self.windows.popitem(last=False)
        return count < self.settings.api_requests_per_minute

    @staticmethod
    def _secure(response: Response) -> Response:
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; font-src 'self' data:; "
            "connect-src 'self' http://127.0.0.1:8000 http://localhost:8000; "
            "worker-src 'self' blob:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
        )
        return response
