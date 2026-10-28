"""Tenant-scoped API key lifecycle endpoints."""

from __future__ import annotations

from datetime import timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select

from ...audit import record_audit
from ...config import get_settings
from ...models.db import ApiKeyRow, Database, Tenant
from ...models.domain import utcnow
from ..auth import API_KEY_ROLES, Principal, require_admin
from ..deps import get_db
from ..key_service import issue_api_key
from ..schemas import ApiKeyCreate, ApiKeyCreated, ApiKeyOut

router = APIRouter()


def _out(row: ApiKeyRow) -> ApiKeyOut:
    return ApiKeyOut(
        id=row.id,
        tenant_id=row.tenant_id,
        name=row.name,
        key_prefix=row.key_prefix,
        role=row.role,
        subject=row.subject,
        created_by=row.created_by,
        created_at=row.created_at,
        expires_at=row.expires_at,
        last_used_at=row.last_used_at,
        revoked_at=row.revoked_at,
    )


def _created(row: ApiKeyRow, token: str) -> ApiKeyCreated:
    return ApiKeyCreated(**_out(row).model_dump(), api_key=token)


def _resolve_tenant(principal: Principal, requested: str | None, database: Database) -> str:
    if not principal.tenant_wildcard:
        if requested and requested != principal.tenant_id:
            raise HTTPException(status_code=404, detail="tenant not found")
        tenant_id = principal.tenant_id
    else:
        tenant_id = requested
    if not tenant_id:
        raise HTTPException(status_code=400, detail="tenant_id is required")
    with database.session() as session:
        if session.get(Tenant, tenant_id) is None:
            raise HTTPException(status_code=404, detail="tenant not found")
    return tenant_id


def _active_key_count(session, tenant_id: str) -> int:
    now = utcnow()
    return int(
        session.scalar(
            select(func.count())
            .select_from(ApiKeyRow)
            .where(
                ApiKeyRow.tenant_id == tenant_id,
                ApiKeyRow.revoked_at.is_(None),
                (ApiKeyRow.expires_at.is_(None)) | (ApiKeyRow.expires_at > now),
            )
        )
        or 0
    )


def _issue(
    database: Database,
    principal: Principal,
    *,
    tenant_id: str,
    name: str,
    role: str,
    days: int | None,
    action: str,
    allow_one_over: bool = False,
) -> ApiKeyCreated:
    if role not in API_KEY_ROLES:
        raise HTTPException(status_code=422, detail="invalid API key role")
    expires_at = (
        utcnow() + timedelta(days=days) if days is not None else None
    )
    with database.session() as session:
        settings = get_settings()
        limit = settings.api_key_max_per_tenant + (1 if allow_one_over else 0)
        if _active_key_count(session, tenant_id) >= limit:
            raise HTTPException(
                status_code=409,
                detail=f"tenant already has {settings.api_key_max_per_tenant} active API keys",
            )
        row, token = issue_api_key(
            session,
            tenant_id=tenant_id,
            name=name,
            role=role,
            subject=f"{principal.subject}:{name}",
            created_by=principal.subject,
            expires_at=expires_at,
        )
        record_audit(
            session,
            principal,
            action=action,
            resource_type="api_key",
            resource_id=row.id,
            tenant_id=tenant_id,
            detail={
                "name": name,
                "prefix": row.key_prefix,
                "role": role,
                "expires_at": expires_at.isoformat() if expires_at else None,
            },
        )
        return _created(row, token)


@router.post("/v1/api-keys", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
def create_api_key(
    payload: ApiKeyCreate,
    database: Database = Depends(get_db),
    principal: Principal = Depends(require_admin),
) -> ApiKeyCreated:
    tenant_id = _resolve_tenant(principal, payload.tenant_id, database)
    return _issue(
        database,
        principal,
        tenant_id=tenant_id,
        name=payload.name.strip(),
        role=payload.role,
        days=payload.expires_in_days,
        action="api_key.created",
    )


@router.get("/v1/api-keys", response_model=list[ApiKeyOut])
def list_api_keys(
    tenant_id: str | None = Query(default=None),
    include_revoked: bool = Query(default=False),
    database: Database = Depends(get_db),
    principal: Principal = Depends(require_admin),
) -> list[ApiKeyOut]:
    scoped = _resolve_tenant(principal, tenant_id, database)
    with database.session() as session:
        statement = (
            select(ApiKeyRow)
            .where(ApiKeyRow.tenant_id == scoped)
            .order_by(ApiKeyRow.created_at.desc())
        )
        if not include_revoked:
            statement = statement.where(ApiKeyRow.revoked_at.is_(None))
        return [_out(row) for row in session.scalars(statement).all()]


@router.delete("/v1/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_api_key(
    key_id: str,
    database: Database = Depends(get_db),
    principal: Principal = Depends(require_admin),
) -> None:
    with database.session() as session:
        row = session.get(ApiKeyRow, key_id)
        if row is None:
            raise HTTPException(status_code=404, detail="API key not found")
        principal.ensure_tenant(row.tenant_id)
        if row.revoked_at is None:
            row.revoked_at = utcnow()
            row.revoked_by = principal.subject
            record_audit(
                session,
                principal,
                action="api_key.revoked",
                resource_type="api_key",
                resource_id=row.id,
                tenant_id=row.tenant_id,
                detail={"name": row.name, "prefix": row.key_prefix},
            )


@router.post(
    "/v1/api-keys/{key_id}/rotate",
    response_model=ApiKeyCreated,
    status_code=status.HTTP_201_CREATED,
)
def rotate_api_key(
    key_id: str,
    database: Database = Depends(get_db),
    principal: Principal = Depends(require_admin),
) -> ApiKeyCreated:
    with database.session() as session:
        row = session.get(ApiKeyRow, key_id)
        if row is None or row.revoked_at is not None:
            raise HTTPException(status_code=404, detail="API key not found")
        principal.ensure_tenant(row.tenant_id)
        tenant_id = row.tenant_id
        name = row.name
        role = row.role
        expires_at = row.expires_at

    days = None
    if expires_at is not None:
        expires_at = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
        days = max(1, (expires_at - utcnow()).days)
    created = _issue(
        database,
        principal,
        tenant_id=tenant_id,
        name=name,
        role=role,
        days=days,
        action="api_key.created",
        allow_one_over=True,
    )

    with database.session() as session:
        row = session.get(ApiKeyRow, key_id)
        if row is not None and row.revoked_at is None:
            row.revoked_at = utcnow()
            row.revoked_by = principal.subject
            record_audit(
                session,
                principal,
                action="api_key.revoked",
                resource_type="api_key",
                resource_id=row.id,
                tenant_id=tenant_id,
                detail={"name": name, "prefix": row.key_prefix, "rotated": True},
            )
    return created
