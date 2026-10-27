"""Tenant endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from ...audit import record_audit
from ...models.db import Database, Tenant, new_id
from ...models.domain import utcnow
from ..auth import Principal, require_admin, require_viewer
from ..deps import get_db
from ..schemas import TenantCreate, TenantOut

router = APIRouter()


@router.post("/v1/tenants", response_model=TenantOut, status_code=status.HTTP_201_CREATED)
def create_tenant(
    payload: TenantCreate,
    database: Database = Depends(get_db),
    principal: Principal = Depends(require_admin),
) -> TenantOut:
    if not principal.tenant_wildcard:
        raise HTTPException(
            status_code=403, detail="only a deployment administrator can create tenants"
        )
    with database.session() as session:
        tenant = Tenant(
            id=new_id("ten"),
            name=payload.name,
            jurisdiction=payload.jurisdiction.lower(),
            created_at=utcnow(),
        )
        session.add(tenant)
        session.flush()
        record_audit(
            session,
            principal,
            action="tenant.created",
            resource_type="tenant",
            resource_id=tenant.id,
            tenant_id=tenant.id,
            detail={"jurisdiction": tenant.jurisdiction},
        )
        return TenantOut.model_validate(tenant)


@router.get("/v1/tenants", response_model=list[TenantOut])
def list_tenants(
    database: Database = Depends(get_db),
    principal: Principal = Depends(require_viewer),
) -> list[TenantOut]:
    with database.session() as session:
        statement = select(Tenant).order_by(Tenant.created_at)
        if not principal.tenant_wildcard:
            statement = statement.where(Tenant.id == principal.tenant_id)
        rows = session.scalars(statement).all()
        return [TenantOut.model_validate(row) for row in rows]


@router.get("/v1/tenants/{tenant_id}", response_model=TenantOut)
def get_tenant(
    tenant_id: str,
    database: Database = Depends(get_db),
    principal: Principal = Depends(require_viewer),
) -> TenantOut:
    principal.ensure_tenant(tenant_id)
    with database.session() as session:
        tenant = session.get(Tenant, tenant_id)
        if tenant is None:
            raise HTTPException(status_code=404, detail="tenant not found")
        return TenantOut.model_validate(tenant)
