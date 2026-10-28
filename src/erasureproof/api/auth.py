"""Authentication, tenant isolation, and role-based access control.

Three modes are supported:

``disabled``
    Local development only. Every request is an unrestricted administrator.
``api_key``
    Static bearer tokens configured through ``ERASUREPROOF_API_KEYS``.
``oidc``
    RS256/RS384/RS512 JWTs validated against an OIDC issuer and cached JWKS.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import threading
import time
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select

from ..config import Settings
from ..models.db import ApiKeyRow, get_database
from ..models.domain import utcnow
from .deps import get_app_settings

_ROLE_LEVEL = {"viewer": 1, "operator": 2, "admin": 3}
_JWKS_LOCK = threading.Lock()
_JWKS_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
API_KEY_PREFIX = "ep_live_"
API_KEY_ROLES = {"viewer", "operator", "admin"}


def generate_api_key() -> str:
    """Return a high-entropy API key. Only the holder ever sees this value."""

    return API_KEY_PREFIX + secrets.token_urlsafe(32)


def hash_api_key(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def api_key_prefix(token: str) -> str:
    return token[:16]


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


@dataclass(frozen=True)
class Principal:
    subject: str
    role: str
    tenant_id: str | None
    method: str
    credential_id: str | None = None

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def tenant_wildcard(self) -> bool:
        return self.tenant_id == "*"

    def require(self, minimum: str) -> None:
        if _ROLE_LEVEL.get(self.role, 0) < _ROLE_LEVEL[minimum]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"role {minimum} or higher is required",
            )

    def ensure_tenant(self, tenant_id: str | None) -> None:
        if tenant_id and not self.tenant_wildcard and tenant_id != self.tenant_id:
            raise HTTPException(status_code=404, detail="tenant not found")


def _unauthorized(detail: str = "authentication required") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _bearer_token(authorization: str | None, api_key: str | None) -> str | None:
    if api_key:
        return api_key.strip()
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def _configured_api_keys(settings: Settings) -> list[dict[str, Any]]:
    raw = settings.api_keys.strip()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=503, detail="API key configuration is invalid") from exc
    if not isinstance(parsed, list):
        raise HTTPException(status_code=503, detail="API key configuration is invalid")
    entries: list[dict[str, Any]] = []
    for item in parsed:
        if not isinstance(item, dict) or not item.get("key"):
            raise HTTPException(status_code=503, detail="API key configuration is invalid")
        role = str(item.get("role", "viewer")).lower()
        if role not in _ROLE_LEVEL:
            raise HTTPException(status_code=503, detail="API key role is invalid")
        tenant = item.get("tenant_id", item.get("tenant"))
        if tenant in {None, ""}:
            raise HTTPException(status_code=503, detail="API key tenant is missing")
        tenant = str(tenant)
        if tenant == "*" and role != "admin":
            raise HTTPException(
                status_code=503,
                detail="only admin API keys may use a wildcard tenant",
            )
        entries.append(
            {
                "key": str(item["key"]),
                "role": role,
                "tenant_id": tenant,
                "subject": str(item.get("subject", item.get("name", "api-key"))),
            }
        )
    return entries


def _static_api_key_principal(token: str, settings: Settings) -> Principal | None:
    matched: dict[str, Any] | None = None
    for entry in _configured_api_keys(settings):
        if hmac.compare_digest(token, entry["key"]):
            matched = entry
    if matched is None:
        return None
    return Principal(
        subject=matched["subject"],
        role=matched["role"],
        tenant_id=matched["tenant_id"],
        method="api_key",
    )


def _database_api_key_principal(token: str) -> Principal | None:
    digest = hash_api_key(token)
    database = get_database()
    now = utcnow()
    with database.session() as session:
        row = session.scalar(select(ApiKeyRow).where(ApiKeyRow.key_hash == digest))
        if row is None or row.revoked_at is not None:
            return None
        expires_at = _aware(row.expires_at)
        if expires_at is not None and expires_at <= now:
            raise _unauthorized("API key expired")
        last_used = _aware(row.last_used_at)
        if last_used is None or (now - last_used).total_seconds() >= 60:
            row.last_used_at = now
        return Principal(
            subject=row.subject,
            role=row.role,
            tenant_id=row.tenant_id,
            method="api_key",
            credential_id=row.id,
        )


def _api_key_principal(token: str, settings: Settings) -> Principal:
    static = _static_api_key_principal(token, settings)
    if static is not None:
        return static
    try:
        principal = _database_api_key_principal(token)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="API key store unavailable") from exc
    if principal is None:
        raise _unauthorized("invalid API key")
    return principal


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _rate_limit_key(request: Request, token: str | None) -> str:
    if token:
        return "key:" + hashlib.sha256(token.encode()).hexdigest()[:16]
    client = request.client.host if request.client else "unknown"
    return "ip:" + client


def _fetch_jwks(url: str, cache_seconds: int) -> dict[str, Any]:
    now = time.time()
    with _JWKS_LOCK:
        cached = _JWKS_CACHE.get(url)
        if cached and cached[0] > now:
            return cached[1]
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=10) as response:
        raw = response.read(2_000_000)
    data = json.loads(raw)
    if not isinstance(data, dict) or not isinstance(data.get("keys"), list):
        raise ValueError("invalid JWKS document")
    with _JWKS_LOCK:
        _JWKS_CACHE[url] = (now + max(cache_seconds, 30), data)
    return data


def _role_from_claims(claims: dict[str, Any], settings: Settings) -> str:
    value = claims.get(settings.oidc_role_claim)
    roles = value if isinstance(value, list) else [value]
    valid = [str(role).lower() for role in roles if str(role).lower() in _ROLE_LEVEL]
    if not valid:
        return settings.oidc_default_role.lower()
    return max(valid, key=lambda role: _ROLE_LEVEL[role])


def _verify_oidc_token(token: str, settings: Settings) -> Principal:
    try:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding, rsa
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise HTTPException(
            status_code=503,
            detail="OIDC support requires the cryptography package",
        ) from exc

    if not (settings.oidc_issuer and settings.oidc_audience and settings.oidc_jwks_url):
        raise HTTPException(status_code=503, detail="OIDC configuration is incomplete")

    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
        header = json.loads(_b64url_decode(header_b64))
        claims = json.loads(_b64url_decode(payload_b64))
        signature = _b64url_decode(signature_b64)
    except (ValueError, json.JSONDecodeError) as exc:
        raise _unauthorized("malformed bearer token") from exc

    algorithm = str(header.get("alg", ""))
    allowed = {item.strip() for item in settings.oidc_algorithms.split(",") if item.strip()}
    if algorithm not in allowed or algorithm not in {"RS256", "RS384", "RS512"}:
        raise _unauthorized("unsupported token algorithm")
    key_id = header.get("kid")
    if not key_id:
        raise _unauthorized("token key id is missing")

    jwks = _fetch_jwks(settings.oidc_jwks_url, settings.oidc_jwks_cache_seconds)
    jwk = next(
        (item for item in jwks["keys"] if item.get("kid") == key_id and item.get("kty") == "RSA"),
        None,
    )
    if jwk is None:
        with _JWKS_LOCK:
            _JWKS_CACHE.pop(settings.oidc_jwks_url, None)
        jwks = _fetch_jwks(settings.oidc_jwks_url, settings.oidc_jwks_cache_seconds)
        jwk = next(
            (
                item
                for item in jwks["keys"]
                if item.get("kid") == key_id and item.get("kty") == "RSA"
            ),
            None,
        )
    if jwk is None:
        raise _unauthorized("signing key not found")

    hash_algorithm = {
        "RS256": hashes.SHA256,
        "RS384": hashes.SHA384,
        "RS512": hashes.SHA512,
    }[algorithm]
    try:
        public_key = rsa.RSAPublicNumbers(
            int.from_bytes(_b64url_decode(jwk["e"]), "big"),
            int.from_bytes(_b64url_decode(jwk["n"]), "big"),
        ).public_key()
        public_key.verify(
            signature,
            f"{header_b64}.{payload_b64}".encode(),
            padding.PKCS1v15(),
            hash_algorithm(),
        )
    except Exception as exc:
        raise _unauthorized("token signature verification failed") from exc

    now = time.time()
    skew = settings.oidc_clock_skew_seconds
    try:
        if float(claims["exp"]) + skew < now:
            raise _unauthorized("token has expired")
        if "nbf" in claims and float(claims["nbf"]) - skew > now:
            raise _unauthorized("token is not valid yet")
    except (KeyError, TypeError, ValueError) as exc:
        raise _unauthorized("token lifetime claims are invalid") from exc
    if claims.get("iss") != settings.oidc_issuer:
        raise _unauthorized("token issuer is invalid")
    audience = claims.get("aud")
    audiences = audience if isinstance(audience, list) else [audience]
    if settings.oidc_audience not in audiences:
        raise _unauthorized("token audience is invalid")

    subject = str(claims.get("sub") or claims.get("email") or "")
    if not subject:
        raise _unauthorized("token subject is missing")
    tenant = claims.get(settings.oidc_tenant_claim)
    if tenant in {None, ""}:
        raise _unauthorized("token is not scoped to a tenant")
    role = _role_from_claims(claims, settings)
    if tenant == "*" and role != "admin":
        raise _unauthorized("only administrator tokens may use a wildcard tenant")
    return Principal(
        subject=subject,
        role=role,
        tenant_id=str(tenant),
        method="oidc",
    )


def authenticate(
    request: Request,
    authorization: str | None = Header(default=None),
    api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> Principal:
    settings = get_app_settings()
    mode = settings.auth_mode.lower()
    if mode == "disabled":
        return Principal(subject="local-dev", role="admin", tenant_id="*", method="disabled")
    if mode not in {"api_key", "oidc"}:
        raise HTTPException(status_code=503, detail="authentication mode is invalid")

    token = _bearer_token(authorization, api_key)
    if not token:
        raise _unauthorized()
    request.state.rate_limit_key = _rate_limit_key(request, token)
    if mode == "api_key":
        return _api_key_principal(token, settings)
    return _verify_oidc_token(token, settings)


def require_viewer(principal: Principal = Depends(authenticate)) -> Principal:
    principal.require("viewer")
    return principal


def require_operator(principal: Principal = Depends(authenticate)) -> Principal:
    principal.require("operator")
    return principal


def require_admin(principal: Principal = Depends(authenticate)) -> Principal:
    principal.require("admin")
    return principal
