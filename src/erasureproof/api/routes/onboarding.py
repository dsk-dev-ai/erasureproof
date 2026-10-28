"""Public self-service developer onboarding."""

from __future__ import annotations

import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request, status

from ...audit import record_audit
from ...config import get_settings
from ...demo import CURRENT_EMAIL
from ...models.db import get_database
from ...sandbox import create_sandbox_workspace
from ..auth import Principal
from ..key_service import issue_api_key
from ..schemas import SandboxCreate, SandboxOut

router = APIRouter()

_SANDBOX_LOCK = threading.Lock()
_SANDBOX_BY_IP: dict[str, deque[datetime]] = defaultdict(deque)
_SANDBOX_GLOBAL: deque[datetime] = deque()


def _client_ip(request: Request) -> str:
    settings = get_settings()
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


def _reserve_sandbox(ip: str) -> None:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24)
    with _SANDBOX_LOCK:
        while _SANDBOX_GLOBAL and _SANDBOX_GLOBAL[0] < cutoff:
            _SANDBOX_GLOBAL.popleft()
        per_ip = _SANDBOX_BY_IP[ip]
        while per_ip and per_ip[0] < cutoff:
            per_ip.popleft()
        if (
            settings.sandbox_daily_limit > 0
            and len(_SANDBOX_GLOBAL) >= settings.sandbox_daily_limit
        ):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="daily sandbox limit reached; try again tomorrow",
                headers={"Retry-After": "3600"},
            )
        if (
            settings.sandbox_per_ip_daily_limit > 0
            and len(per_ip) >= settings.sandbox_per_ip_daily_limit
        ):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="sandbox limit reached for this client; try again tomorrow",
                headers={"Retry-After": "3600"},
            )
        _SANDBOX_GLOBAL.append(now)
        per_ip.append(now)


@router.post("/v1/onboarding/sandbox", response_model=SandboxOut, status_code=201)
def create_sandbox(payload: SandboxCreate, request: Request) -> SandboxOut:
    settings = get_settings()
    if not settings.self_serve_enabled:
        raise HTTPException(status_code=404, detail="self-service onboarding is disabled")

    _reserve_sandbox(_client_ip(request))

    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.sandbox_ttl_hours)
    tenant_name = f"{payload.workspace_name.strip()} (sandbox)"
    tenant_id, request_id, _audit_at = create_sandbox_workspace(
        tenant_name=tenant_name,
        jurisdiction=payload.jurisdiction,
        settings=settings,
    )

    principal = Principal(
        subject="sandbox-bootstrap",
        role="admin",
        tenant_id=tenant_id,
        method="self_serve",
    )
    database = get_database()
    with database.session() as session:
        row, token = issue_api_key(
            session,
            tenant_id=tenant_id,
            name="Sandbox administrator",
            role="admin",
            subject=f"sandbox:{tenant_id}",
            created_by="sandbox-bootstrap",
            expires_at=expires_at,
        )
        record_audit(
            session,
            principal,
            action="sandbox.created",
            resource_type="tenant",
            resource_id=tenant_id,
            tenant_id=tenant_id,
            request_id=request_id,
            detail={
                "jurisdiction": payload.jurisdiction,
                "key_id": row.id,
                "key_prefix": row.key_prefix,
                "expires_at": expires_at.isoformat(),
            },
        )

    return SandboxOut(
        tenant_id=tenant_id,
        tenant_name=tenant_name,
        api_key=token,
        key_id=row.id,
        key_prefix=row.key_prefix,
        expires_at=expires_at,
        sample_request_id=request_id,
        sample_email=CURRENT_EMAIL,
        quickstart={
            "docs": "/docs",
            "console": "/console",
            "run_audit": f"POST /v1/requests/{request_id}/run?remediate=false",
            "get_attestation": f"GET /v1/requests/{request_id}/attestation",
            "curl": (
                "curl -s -X POST "
                "'$BASE_URL/v1/requests/"
                + request_id
                + "/run?remediate=false' -H 'Authorization: Bearer $ERASUREPROOF_API_KEY'"
            ),
        },
    )
