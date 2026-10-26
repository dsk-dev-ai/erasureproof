"""Connector registry."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.db import ConnectorRow
from .base import BaseConnector
from .control import ControlConnector
from .filesystem import FilesystemConnector
from .postgres import PostgresConnector
from .s3 import LocalObjectConnector, S3Connector
from .sql import SQLConnector

Factory = Callable[..., BaseConnector]

_REGISTRY: dict[str, Factory] = {
    "sql": SQLConnector,
    "postgres": PostgresConnector,
    "control": ControlConnector,
    "filesystem": FilesystemConnector,
    "workspace": FilesystemConnector,
    "s3": S3Connector,
    "local": LocalObjectConnector,
}


def register_connector(type_name: str, factory: Factory) -> None:
    _REGISTRY[type_name.lower()] = factory


def connector_types() -> list[str]:
    return sorted(_REGISTRY)


def create_connector(
    connector_id: str,
    type_name: str,
    system_id: str,
    config: dict[str, Any] | None = None,
    evidence_store: Any | None = None,
) -> BaseConnector:
    key = type_name.lower()
    if key not in _REGISTRY:
        raise ValueError(f"Unknown connector type: {type_name!r}")
    return _REGISTRY[key](
        connector_id=connector_id,
        system_id=system_id,
        config=config or {},
        evidence_store=evidence_store,
    )


def from_rows(rows: list[ConnectorRow], evidence_store: Any | None = None) -> list[BaseConnector]:
    connectors: list[BaseConnector] = []
    for row in rows:
        if not row.enabled:
            continue
        system_id = str((row.config or {}).get("system_id", row.name))
        connectors.append(
            create_connector(
                connector_id=row.id,
                type_name=row.type,
                system_id=system_id,
                config=row.config or {},
                evidence_store=evidence_store,
            )
        )
    return connectors


def load_for_tenant(
    session: Session, tenant_id: str, evidence_store: Any | None = None
) -> list[BaseConnector]:
    rows = session.scalars(
        select(ConnectorRow).where(
            ConnectorRow.tenant_id == tenant_id, ConnectorRow.enabled.is_(True)
        )
    ).all()
    return from_rows(list(rows), evidence_store)
