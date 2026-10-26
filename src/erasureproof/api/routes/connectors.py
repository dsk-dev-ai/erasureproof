"""Connector registration endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from ...connectors.registry import connector_types
from ...models.db import ConnectorRow, Database, Tenant, new_id
from ...models.domain import utcnow
from ..deps import get_db
from ..schemas import ConnectorCreate, ConnectorOut

router = APIRouter()


@router.get("/v1/connector-types")
def list_connector_types() -> dict[str, list[str]]:
    return {"types": connector_types()}


@router.post("/v1/connectors", response_model=ConnectorOut, status_code=status.HTTP_201_CREATED)
def create_connector(
    payload: ConnectorCreate, database: Database = Depends(get_db)
) -> ConnectorOut:
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
        return ConnectorOut.model_validate(row)


@router.get("/v1/tenants/{tenant_id}/connectors", response_model=list[ConnectorOut])
def list_connectors(
    tenant_id: str, database: Database = Depends(get_db)
) -> list[ConnectorOut]:
    with database.session() as session:
        rows = session.scalars(
            select(ConnectorRow).where(ConnectorRow.tenant_id == tenant_id)
        ).all()
        return [ConnectorOut.model_validate(row) for row in rows]


@router.delete("/v1/connectors/{connector_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_connector(connector_id: str, database: Database = Depends(get_db)) -> None:
    with database.session() as session:
        row = session.get(ConnectorRow, connector_id)
        if row is None:
            raise HTTPException(status_code=404, detail="connector not found")
        session.delete(row)
