"""HTTP hardening: request IDs, rate limiting, access logs, and metrics."""

from __future__ import annotations

import json
import logging
import re
import threading
import time
import uuid
from collections import defaultdict, deque

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .config import get_settings

_ACCESS_LOG = logging.getLogger("erasureproof.access")
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
_RATE_EVENTS: dict[str, deque[float]] = defaultdict(deque)
_RATE_LOCK = threading.Lock()
_METRICS_LOCK = threading.Lock()
_REQUESTS: dict[tuple[str, str, str], int] = defaultdict(int)
_DURATION_SUM: dict[tuple[str, str], float] = defaultdict(float)
_DURATION_COUNT: dict[tuple[str, str], int] = defaultdict(int)
_IN_FLIGHT = 0
_RATE_LIMITED = 0
_STARTED_AT = time.time()


def _client_key(scope: Scope) -> str:
    client = scope.get("client")
    host = client[0] if client else "unknown"
    if get_settings().trust_proxy_headers:
        forwarded = Headers(scope=scope).get("x-forwarded-for")
        if forwarded:
            host = forwarded.split(",", 1)[0].strip()
    return "ip:" + host


def _prune_rate_events(now: float) -> None:
    if len(_RATE_EVENTS) <= 10_000:
        return
    for key, events in list(_RATE_EVENTS.items()):
        if not events or events[-1] <= now - 60:
            _RATE_EVENTS.pop(key, None)


def _rate_limited(scope: Scope) -> tuple[bool, int, int, int]:
    limit = get_settings().rate_limit_per_minute
    if limit <= 0 or not scope.get("path", "").startswith("/v1"):
        return False, 0, 0, 0
    key = _client_key(scope)
    now = time.monotonic()
    with _RATE_LOCK:
        _prune_rate_events(now)
        events = _RATE_EVENTS[key]
        while events and events[0] <= now - 60:
            events.popleft()
        if len(events) >= limit:
            retry_after = max(1, int(60 - (now - events[0])))
            return True, limit, retry_after, 0
        events.append(now)
        remaining = max(0, limit - len(events))
    return False, limit, 0, remaining


def _route_label(scope: Scope) -> str:
    route = scope.get("route")
    path = getattr(route, "path", None)
    if path:
        return str(path)
    raw = scope.get("path", "")
    if raw.startswith("/console"):
        return "/console/{path}"
    return "<unmatched>"


def _record(method: str, route: str, status: int, duration: float) -> None:
    global _IN_FLIGHT
    with _METRICS_LOCK:
        _REQUESTS[(method, route, str(status))] += 1
        _DURATION_SUM[(method, route)] += duration
        _DURATION_COUNT[(method, route)] += 1
        _IN_FLIGHT -= 1


def _prom_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def render_metrics(version: str) -> str:
    with _METRICS_LOCK:
        requests = dict(_REQUESTS)
        duration_sum = dict(_DURATION_SUM)
        duration_count = dict(_DURATION_COUNT)
        in_flight = _IN_FLIGHT
        rate_limited = _RATE_LIMITED
    lines = [
        "# HELP erasureproof_build_info Build and version information.",
        "# TYPE erasureproof_build_info gauge",
        f'erasureproof_build_info{{version="{_prom_label(version)}"}} 1',
        "# HELP erasureproof_process_start_time_seconds Process start time.",
        "# TYPE erasureproof_process_start_time_seconds gauge",
        f"erasureproof_process_start_time_seconds {_STARTED_AT}",
        "# HELP erasureproof_http_requests_in_flight Requests currently being served.",
        "# TYPE erasureproof_http_requests_in_flight gauge",
        f"erasureproof_http_requests_in_flight {in_flight}",
        "# HELP erasureproof_http_requests_total HTTP requests by method, route, and status.",
        "# TYPE erasureproof_http_requests_total counter",
    ]
    for (method, route, status), count in sorted(requests.items()):
        lines.append(
            "erasureproof_http_requests_total"
            f'{{method="{_prom_label(method)}",route="{_prom_label(route)}",'
            f'status="{_prom_label(status)}"}} {count}'
        )
    lines.extend(
        [
            "# HELP erasureproof_http_request_duration_seconds HTTP request duration.",
            "# TYPE erasureproof_http_request_duration_seconds summary",
        ]
    )
    for (method, route), total in sorted(duration_sum.items()):
        labels = f'method="{_prom_label(method)}",route="{_prom_label(route)}"'
        lines.append(f"erasureproof_http_request_duration_seconds_sum{{{labels}}} {total:.6f}")
        lines.append(
            "erasureproof_http_request_duration_seconds_count"
            f"{{{labels}}} {duration_count.get((method, route), 0)}"
        )
    lines.extend(
        [
            "# HELP erasureproof_rate_limited_total Requests rejected by the local limiter.",
            "# TYPE erasureproof_rate_limited_total counter",
            f"erasureproof_rate_limited_total {rate_limited}",
        ]
    )
    return "\n".join(lines) + "\n"


class ProductionMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        settings = get_settings()
        headers = Headers(scope=scope)
        incoming = headers.get("x-request-id", "")
        request_id = incoming if _REQUEST_ID.match(incoming) else uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id

        global _IN_FLIGHT, _RATE_LIMITED
        with _METRICS_LOCK:
            _IN_FLIGHT += 1

        start = time.perf_counter()
        method = scope.get("method", "GET")

        limited, limit, retry_after, remaining = _rate_limited(scope)
        if limited:
            with _METRICS_LOCK:
                _RATE_LIMITED += 1
            response = JSONResponse(
                {"detail": "rate limit exceeded", "request_id": request_id},
                status_code=429,
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(retry_after),
                },
            )
            await response(scope, receive, send)
            _record(method, "<rate-limited>", 429, time.perf_counter() - start)
            return

        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                mutable = MutableHeaders(scope=message)
                mutable["X-Request-ID"] = request_id
                mutable["X-Process-Time-Ms"] = f"{(time.perf_counter() - start) * 1000:.1f}"
                if limit > 0 and scope.get("path", "").startswith("/v1"):
                    mutable["X-RateLimit-Limit"] = str(limit)
                    mutable["X-RateLimit-Remaining"] = str(remaining)
                if settings.security_headers_enabled:
                    mutable["X-Content-Type-Options"] = "nosniff"
                    mutable["X-Frame-Options"] = "DENY"
                    mutable["Referrer-Policy"] = "no-referrer"
                    mutable["Permissions-Policy"] = (
                        "camera=(), microphone=(), geolocation=(), payment=()"
                    )
                    mutable["Cross-Origin-Opener-Policy"] = "same-origin"
                    if scope.get("path", "").startswith("/console"):
                        mutable["Content-Security-Policy"] = (
                            "default-src 'self'; script-src 'self'; style-src 'self' "
                            "'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' "
                            "data:; connect-src 'self'; object-src 'none'; base-uri 'self'; "
                            "frame-ancestors 'none'"
                        )
                if settings.hsts_seconds > 0:
                    mutable["Strict-Transport-Security"] = (
                        f"max-age={settings.hsts_seconds}; includeSubDomains"
                    )
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            duration = time.perf_counter() - start
            route = _route_label(scope)
            _record(method, route, 500, duration)
            if settings.access_log_enabled:
                _ACCESS_LOG.exception(
                    json.dumps(
                        {
                            "event": "http.request.error",
                            "request_id": request_id,
                            "method": method,
                            "route": route,
                            "duration_ms": round(duration * 1000, 1),
                        }
                    )
                )
            raise
        duration = time.perf_counter() - start
        route = _route_label(scope)
        _record(method, route, status_code, duration)
        if settings.access_log_enabled:
            _ACCESS_LOG.info(
                json.dumps(
                    {
                        "event": "http.request",
                        "request_id": request_id,
                        "method": method,
                        "route": route,
                        "status": status_code,
                        "duration_ms": round(duration * 1000, 1),
                    },
                    separators=(",", ":"),
                )
            )
