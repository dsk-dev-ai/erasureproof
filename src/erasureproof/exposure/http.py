"""Public-web HTTP client with SSRF and robots.txt guardrails."""

from __future__ import annotations

import ipaddress
import socket
import threading
import time
from dataclasses import dataclass, field
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import (
    HTTPRedirectHandler,
    Request,
    build_opener,
)
from urllib.robotparser import RobotFileParser


class UnsafeUrlError(ValueError):
    """Raised when a URL points at a non-public or unsupported destination."""


class FetchError(RuntimeError):
    """Raised when a public fetch fails."""


@dataclass(slots=True)
class HttpResponse:
    url: str
    status: int
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    truncated: bool = False

    @property
    def content_type(self) -> str:
        return self.headers.get("content-type", "").split(";")[0].strip().lower()

    @property
    def text(self) -> str:
        charset = "utf-8"
        content_type = self.headers.get("content-type", "")
        if "charset=" in content_type:
            charset = content_type.split("charset=")[-1].split(";")[0].strip()
        try:
            return self.body.decode(charset, errors="replace")
        except LookupError:
            return self.body.decode("utf-8", errors="replace")


def validate_url(url: str, allow_private: bool = False) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeUrlError(f"unsupported scheme: {parsed.scheme or '(none)'}")
    if parsed.username or parsed.password:
        raise UnsafeUrlError("credentials in URLs are not allowed")
    host = parsed.hostname
    if not host:
        raise UnsafeUrlError("URL has no host")
    if host.lower() in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        raise UnsafeUrlError("local hosts are not allowed")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        }
    except OSError as exc:
        raise UnsafeUrlError(f"cannot resolve host: {exc}") from exc
    if not addresses:
        raise UnsafeUrlError("host resolved to no addresses")
    if not allow_private:
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if not ip.is_global:
                raise UnsafeUrlError(f"non-public destination: {address}")
    return url


class _SafeRedirectHandler(HTTPRedirectHandler):
    def __init__(self, allow_private: bool) -> None:
        super().__init__()
        self.allow_private = allow_private

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        validate_url(urljoin(req.full_url, newurl), self.allow_private)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class _RobotsCache:
    def __init__(self, client: HttpClient) -> None:
        self.client = client
        self._cache: dict[str, RobotFileParser | None] = {}
        self._lock = threading.Lock()

    def allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        with self._lock:
            if origin in self._cache:
                parser = self._cache[origin]
            else:
                parser = self._load(origin)
                self._cache[origin] = parser
        if parser is None:
            return True
        return parser.can_fetch("*", url)

    def _load(self, origin: str) -> RobotFileParser | None:
        try:
            response = self.client.get(
                f"{origin}/robots.txt",
                check_robots=False,
                allow_private=self.client.allow_private,
            )
        except (FetchError, UnsafeUrlError):
            return None
        if response.status >= 400:
            return None
        parser = RobotFileParser()
        parser.set_url(f"{origin}/robots.txt")
        parser.parse(response.text.splitlines())
        return parser


class HttpClient:
    def __init__(
        self,
        timeout: float = 15.0,
        max_bytes: int = 2_000_000,
        user_agent: str = "ErasureProof/0.2",
        allow_private: bool = False,
        rate_limit_seconds: float = 1.0,
    ) -> None:
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.user_agent = user_agent
        self.allow_private = allow_private
        self.rate_limit_seconds = rate_limit_seconds
        self._last_request: dict[str, float] = {}
        self._lock = threading.Lock()
        self.robots = _RobotsCache(self)

    def _wait(self, host: str) -> None:
        with self._lock:
            last = self._last_request.get(host, 0.0)
            wait = max(0.0, self.rate_limit_seconds - (time.monotonic() - last))
            self._last_request[host] = time.monotonic() + wait
        if wait:
            time.sleep(wait)

    def get(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        check_robots: bool = True,
        allow_private: bool | None = None,
    ) -> HttpResponse:
        allow = self.allow_private if allow_private is None else allow_private
        normalised = validate_url(url, allow)
        if check_robots and not self.robots.allowed(normalised):
            raise FetchError(f"robots.txt disallows {normalised}")
        parsed = urlparse(normalised)
        self._wait(parsed.netloc)
        request_headers = {"User-Agent": self.user_agent, "Accept": "*/*"}
        request_headers.update(headers or {})
        request = Request(normalised, headers=request_headers, method="GET")
        opener = build_opener(_SafeRedirectHandler(allow))
        try:
            with opener.open(request, timeout=self.timeout) as response:
                body = response.read(self.max_bytes + 1)
                return HttpResponse(
                    url=response.geturl(),
                    status=int(response.status),
                    headers={key.lower(): value for key, value in response.headers.items()},
                    body=body[: self.max_bytes],
                    truncated=len(body) > self.max_bytes,
                )
        except HTTPError as exc:
            body = exc.read(self.max_bytes + 1)
            return HttpResponse(
                url=exc.geturl(),
                status=int(exc.code),
                headers={key.lower(): value for key, value in exc.headers.items()},
                body=body[: self.max_bytes],
                truncated=len(body) > self.max_bytes,
            )
        except (URLError, TimeoutError, OSError) as exc:
            raise FetchError(f"fetch failed for {normalised}: {exc}") from exc

    def post_json(
        self,
        url: str,
        payload: dict,
        headers: dict[str, str] | None = None,
    ) -> HttpResponse:
        import json

        normalised = validate_url(url, self.allow_private)
        parsed = urlparse(normalised)
        self._wait(parsed.netloc)
        request_headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        request_headers.update(headers or {})
        request = Request(
            normalised,
            data=json.dumps(payload).encode("utf-8"),
            headers=request_headers,
            method="POST",
        )
        opener = build_opener(_SafeRedirectHandler(self.allow_private))
        try:
            with opener.open(request, timeout=self.timeout) as response:
                body = response.read(self.max_bytes + 1)
                return HttpResponse(
                    url=response.geturl(),
                    status=int(response.status),
                    headers={key.lower(): value for key, value in response.headers.items()},
                    body=body[: self.max_bytes],
                    truncated=len(body) > self.max_bytes,
                )
        except HTTPError as exc:
            body = exc.read(self.max_bytes + 1)
            return HttpResponse(
                url=exc.geturl(),
                status=int(exc.code),
                headers={key.lower(): value for key, value in exc.headers.items()},
                body=body[: self.max_bytes],
                truncated=len(body) > self.max_bytes,
            )
        except (URLError, TimeoutError, OSError) as exc:
            raise FetchError(f"fetch failed for {normalised}: {exc}") from exc
