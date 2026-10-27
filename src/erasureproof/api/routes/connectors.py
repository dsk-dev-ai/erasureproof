"""Connector registration endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from ...audit import record_audit
from ...connectors.registry import connector_types
from ...models.db import ConnectorRow, Database, Tenant, new_id
from ...models.domain import utcnow
from ..auth import Principal, require_admin, require_viewer
from ..deps import get_db
from ..schemas import ConnectorCreate, ConnectorOut

router = APIRouter()

_SENSITIVE = ("password", "passwd", "secret", "token", "key", "dsn", "url", "uri", "credential")


def _redact(value):
    if isinstance(value, dict):
        return {
            key: "[redacted]"
            if any(marker in str(key).lower() for marker in _SENSITIVE)
            else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _connector_out(row: ConnectorRow) -> ConnectorOut:
    return ConnectorOut(
        id=row.id,
        tenant_id=row.tenant_id,
        type=row.type,
        name=row.name,
        config=_redact(row.config or {}),
        enabled=row.enabled,
        created_at=row.created_at,
    )


@router.get("/v1/connector-types")
def list_connector_types(principal: Principal = Depends(require_viewer)) -> dict[str, list[str]]:
    return {"types": connector_types()}


@router.post("/v1/connectors", response_model=ConnectorOut, status_code=status.HTTP_201_CREATED)
def create_connector(
    payload: ConnectorCreate,
    database: Database = Depends(get_db),
    principal: Principal = Depends(require_admin),
) -> ConnectorOut:
    principal.ensure_tenant(payload.tenant_id)
    if payload.type.lower() not in connector_types():
        raise HTTPException(
            status_code=400,
            detail=f"unknown connector type; supported: {', '.join(connector_types())}",
        )
    with database.session() as session:
        if session.get(Tenant, payload.tenant_id) is None:
            raise HTTPException(status_code=404, detail="tenant not found")
        row = ConnectorRow(
            id=new_id("con"),
            tenant_id=payload.tenant_id,
            type=payload.type.lower(),
            name=payload.name,
            config=payload.config,
            enabled=payload.enabled,
            created_at=utcnow(),
        )
        session.add(row)
        session.flush()
        record_audit(
            session,
            principal,
            action="connector.created",
            resource_type="connector",
            resource_id=row.id,
            tenant_id=row.tenant_id,
            detail={"type": row.type, "name": row.name},
        )
        return _connector_out(row)


@router.get("/v1/tenants/{tenant_id}/connectors", response_model=list[ConnectorOut])
def list_connectors(
    tenant_id: str,
    database: Database = Depends(get_db),
    principal: Principal = Depends(require_viewer),
) -> list[ConnectorOut]:
    principal.ensure_tenant(tenant_id)
    with database.session() as session:
        rows = session.scalars(
            select(ConnectorRow).where(ConnectorRow.tenant_id == tenant_id)
        ).all()
        return [_connector_out(row) for row in rows]


@router.delete("/v1/connectors/{connector_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_connector(
    connector_id: str,
    database: Database = Depends(get_db),
    principal: Principal = Depends(require_admin),
) -> None:
    with database.session() as session:
        row = session.get(ConnectorRow, connector_id)
        if row is None:
            raise HTTPException(status_code=404, detail="connector not found")
        principal.ensure_tenant(row.tenant_id)
        record_audit(
            session,
            principal,
            action="connector.deleted",
            resource_type="connector",
            resource_id=row.id,
            tenant_id=row.tenant_id,
            detail={"type": row.type, "name": row.name},
        )
        session.delete(row)
