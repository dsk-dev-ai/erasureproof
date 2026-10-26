"""Postgres connector.

A thin specialisation of the SQL connector. Use it when you want Postgres-aware
behaviour (replicas, logical backups) to be explicit in configuration.
"""

from __future__ import annotations

from typing import Any

from .sql import SQLConnector


class PostgresConnector(SQLConnector):
    type = "postgres"

    def __init__(
        self,
        connector_id: str,
        system_id: str,
        config: dict[str, Any] | None = None,
        evidence_store: Any | None = None,
    ) -> None:
        config = dict(config or {})
        url = str(config.get("url", ""))
        if url.startswith("postgres://"):
            config["url"] = "postgresql+psycopg://" + url[len("postgres://") :]
        elif url.startswith("postgresql://"):
            config["url"] = "postgresql+psycopg://" + url[len("postgresql://") :]
        super().__init__(connector_id, system_id, config, evidence_store)
