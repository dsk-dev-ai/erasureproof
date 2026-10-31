from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from erasureproof.connectors.s3 import LocalObjectConnector
from erasureproof.connectors.sql import SQLConnector
from erasureproof.evidence.store import EvidenceStore
from erasureproof.models.domain import (
    Action,
    Category,
    Identifier,
    IdentifierType,
    ResourceRef,
    State,
    SubjectGraph,
    hash_email,
)

NOW = datetime.now(timezone.utc)
AUDIT_AT = NOW + timedelta(hours=1)


def _subject() -> SubjectGraph:
    return SubjectGraph(
        user_id="u_1",
        identifiers=[
            Identifier(IdentifierType.EMAIL, "alice@example.com"),
            Identifier(IdentifierType.EMAIL_HASH, hash_email("alice@example.com")),
        ],
    )


def _sql_connector(path: Path, store: EvidenceStore | None = None) -> SQLConnector:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            user_id TEXT,
            name TEXT,
            email TEXT,
            phone TEXT,
            email_hash TEXT
        );
        """
    )
    connection.execute(
        "INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?)",
        (
            1,
            "u_1",
            "Alice",
            "alice@example.com",
            "+15550100",
            hash_email("alice@example.com"),
        ),
    )
    connection.execute(
        "INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?)",
        (2, "u_2", "Bob", "bob@example.com", "+15550200", hash_email("bob@example.com")),
    )
    connection.commit()
    connection.close()

    return SQLConnector(
        connector_id="con_sql",
        system_id="account_db",
        evidence_store=store,
        config={
            "url": f"sqlite:///{path}",
            "tables": {
                "customers": {
                    "category": "PRIMARY_ACCOUNT",
                    "pk": "customer_id",
                    "user_id_column": "user_id",
                    "subject_columns": [
                        ["email", "EMAIL"],
                        ["phone", "PHONE"],
                        ["email_hash", "EMAIL_HASH"],
                    ],
                    "pii_fields": ["name", "email", "phone", "email_hash"],
                }
            },
        },
    )


def test_sql_discovery_excludes_decoys(tmp_path) -> None:
    connector = _sql_connector(tmp_path / "app.db", EvidenceStore(tmp_path / "evidence"))
    resources = connector.discover(_subject(), AUDIT_AT)

    assert len(resources) == 1
    record = resources[0]
    assert record.category is Category.PRIMARY_ACCOUNT
    assert record.resource_id == "customers:1"
    assert set(record.exposed_fields) == {"name", "email", "phone", "email_hash"}
    assert record.evidence_id.startswith("ev_")


def test_sql_tombstone_then_delete(tmp_path) -> None:
    connector = _sql_connector(tmp_path / "app.db", EvidenceStore(tmp_path / "evidence"))
    record = connector.discover(_subject(), AUDIT_AT)[0]

    result = connector.remediate(
        record,
        Action.TOMBSTONE,
        ("name", "email", "phone", "email_hash"),
    )
    assert result.success

    verification = connector.verify(record, State.REDACTED)
    assert verification.passed

    rediscovered = connector.discover(_subject(), AUDIT_AT)
    assert len(rediscovered) == 1
    assert rediscovered[0].exposed_fields == []

    deletion = connector.remediate(record, Action.DELETE)
    assert deletion.success
    assert connector.verify(record, State.ABSENT).passed


def test_local_object_connector_filters_time_and_remediates(tmp_path) -> None:
    root = tmp_path / "bucket"
    (root / "exports").mkdir(parents=True)
    (root / "logs").mkdir(parents=True)
    (root / "exports" / "alice.json").write_text(
        json.dumps({"email": "alice@example.com"}), encoding="utf-8"
    )
    (root / "logs" / "app.log").write_text(
        "login email=alice@example.com\n", encoding="utf-8"
    )
    (root / "exports" / "decoy.json").write_text(
        json.dumps({"email": "bob@example.com"}), encoding="utf-8"
    )
    future = root / "exports" / "future.json"
    future.write_text(json.dumps({"email": "alice@example.com"}), encoding="utf-8")
    future_time = (AUDIT_AT + timedelta(days=1)).timestamp()
    os.utime(future, (future_time, future_time))

    connector = LocalObjectConnector(
        connector_id="con_obj",
        system_id="object_store",
        config={
            "backend": "local",
            "root": str(root),
            "categories": {"exports/": "EXPORT", "logs/": "LOG"},
        },
    )

    resources = connector.discover(_subject(), AUDIT_AT)
    ids = {resource.resource_id for resource in resources}
    assert ids == {"exports/alice.json", "logs/app.log"}

    export = next(r for r in resources if r.resource_id == "exports/alice.json")
    assert export.category is Category.EXPORT
    assert connector.remediate(export, Action.REDACT).success
    assert connector.verify(export, State.REDACTED).passed
    assert "alice@example.com" not in (root / "exports" / "alice.json").read_text()

    log = next(r for r in resources if r.resource_id == "logs/app.log")
    assert connector.remediate(log, Action.DELETE).success
    assert connector.verify(log, State.ABSENT).passed
    assert not (root / "logs" / "app.log").exists()


def test_local_object_connector_blocks_path_escape_and_symlinks(tmp_path) -> None:
    root = tmp_path / "bucket"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("alice@example.com", encoding="utf-8")
    (root / "link.txt").symlink_to(outside)

    connector = LocalObjectConnector(
        connector_id="con_obj",
        system_id="object_store",
        config={"backend": "local", "root": str(root)},
    )

    assert connector.discover(_subject(), AUDIT_AT) == []

    bad = ResourceRef(
        "object_store",
        "../outside.txt",
        Category.EXPORT,
        payload={"path": "../outside.txt"},
    )
    result = connector.remediate(bad, Action.DELETE)
    assert result.success is False
    assert outside.exists()
