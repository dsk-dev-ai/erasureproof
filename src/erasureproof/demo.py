"""Seeded end-to-end demo.

Creates a small commerce platform (SQLite + object store + control plane),
runs a GDPR erasure for a fictional subject, remediates every copy, verifies the
result and issues a signed attestation.
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import Settings, get_settings
from .connectors.registry import load_for_tenant
from .core.attestation import AttestationService
from .core.identity import resolve_from_db
from .core.policy import PolicyRegistry
from .evidence.ledger import EvidenceLedger
from .evidence.store import EvidenceStore
from .models.db import (
    ConnectorRow,
    IdentifierRow,
    RequestRow,
    Subject,
    Tenant,
    get_database,
    new_id,
)
from .models.domain import Identifier, IdentifierType, hash_email, utcnow
from .orchestrator.runner import ErasureOrchestrator, RunResult

TENANT_ID = "ten_demo"
SUBJECT_USER_ID = "u_1001"
CURRENT_EMAIL = "alice@example.com"
HISTORICAL_EMAIL = "alice.old@example.com"
CURRENT_PHONE = "+15550100"


@dataclass
class DemoContext:
    tenant_id: str
    subject_id: str
    request_id: str
    audit_at: datetime
    app_db: Path
    bucket_root: Path
    control_path: Path


def _create_app_database(path: Path, audit_at: datetime) -> None:
    if path.exists():
        path.unlink()
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            user_id TEXT,
            name TEXT,
            email TEXT,
            phone TEXT,
            email_hash TEXT,
            created_at TEXT
        );
        CREATE TABLE search_index (
            document_id TEXT PRIMARY KEY,
            user_id TEXT,
            email TEXT,
            display_name TEXT
        );
        CREATE TABLE analytics_events (
            event_id TEXT PRIMARY KEY,
            user_id TEXT,
            email TEXT,
            event TEXT
        );
        CREATE TABLE support_tickets (
            ticket_id TEXT PRIMARY KEY,
            user_id TEXT,
            email TEXT,
            subject TEXT,
            body TEXT
        );
        CREATE TABLE audit_trail (
            audit_id TEXT PRIMARY KEY,
            user_id TEXT,
            action TEXT,
            created_at TEXT
        );
        CREATE TABLE tombstones (
            tombstone_id TEXT PRIMARY KEY,
            user_id TEXT,
            name TEXT,
            email TEXT,
            phone TEXT,
            email_hash TEXT
        );
        """
    )
    created = (audit_at - timedelta(days=400)).isoformat()
    connection.executemany(
        "INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (
                501,
                SUBJECT_USER_ID,
                "Alice Example",
                CURRENT_EMAIL,
                CURRENT_PHONE,
                hash_email(CURRENT_EMAIL),
                created,
            ),
            (
                502,
                "u_2002",
                "Bob Decoy",
                "bob@example.com",
                "+15550200",
                hash_email("bob@example.com"),
                created,
            ),
        ],
    )
    connection.executemany(
        "INSERT INTO search_index VALUES (?, ?, ?, ?)",
        [
            ("doc_9001", SUBJECT_USER_ID, CURRENT_EMAIL, "Alice Example"),
            ("doc_9002", "u_2002", "bob@example.com", "Bob Decoy"),
        ],
    )
    connection.executemany(
        "INSERT INTO analytics_events VALUES (?, ?, ?, ?)",
        [
            ("evt_7001", SUBJECT_USER_ID, HISTORICAL_EMAIL, "checkout"),
            ("evt_7002", "u_2002", "bob@example.com", "checkout"),
        ],
    )
    connection.executemany(
        "INSERT INTO support_tickets VALUES (?, ?, ?, ?, ?)",
        [
            (
                "ticket_42",
                SUBJECT_USER_ID,
                CURRENT_EMAIL,
                "Refund",
                "Customer asked about a refund.",
            ),
            ("ticket_43", "u_2002", "bob@example.com", "Login", "Decoy ticket."),
        ],
    )
    connection.executemany(
        "INSERT INTO audit_trail VALUES (?, ?, ?, ?)",
        [
            ("audit_1", SUBJECT_USER_ID, "login", created),
            ("audit_2", "u_2002", "login", created),
        ],
    )
    connection.executemany(
        "INSERT INTO tombstones VALUES (?, ?, ?, ?, ?, ?)",
        [
            (
                "tomb_1",
                SUBJECT_USER_ID,
                "Alice Example",
                CURRENT_EMAIL,
                CURRENT_PHONE,
                hash_email(CURRENT_EMAIL),
            )
        ],
    )
    connection.commit()
    connection.close()


def _create_bucket(root: Path, audit_at: datetime) -> None:
    if root.exists():
        for path in sorted(root.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
    root.mkdir(parents=True, exist_ok=True)

    files = {
        "exports/user_u_1001_export.json": json.dumps(
            {
                "user_id": SUBJECT_USER_ID,
                "email": CURRENT_EMAIL,
                "phone": CURRENT_PHONE,
                "orders": 3,
            },
            indent=2,
        ),
        "attachments/ticket_42.txt": (
            f"Support attachment for {CURRENT_EMAIL}\n"
            "Order #1001 - refund requested.\n"
        ),
        "logs/app.log": (
            f"2026-01-01 login user={SUBJECT_USER_ID} email={HISTORICAL_EMAIL}\n"
            "2026-01-02 checkout ok\n"
        ),
        "exports/decoy.json": json.dumps(
            {"user_id": "u_2002", "email": "bob@example.com"}, indent=2
        ),
    }
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        timestamp = (audit_at - timedelta(days=10)).timestamp()
        os.utime(path, (timestamp, timestamp))

    future = root / "exports/future_export.json"
    future.write_text(json.dumps({"email": CURRENT_EMAIL}), encoding="utf-8")
    future_timestamp = (audit_at + timedelta(days=1)).timestamp()
    os.utime(future, (future_timestamp, future_timestamp))


def _create_control_plane(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "flows": [
                    {
                        "flow_id": "flow_crm_sync",
                        "system_id": "control_plane",
                        "source": "account_service",
                        "dest": "analytics",
                        "status": "ACTIVE",
                        "subject_ids": [SUBJECT_USER_ID],
                        "subject_values": [CURRENT_EMAIL],
                    }
                ],
                "backups": [
                    {
                        "backup_id": "backup_weekly",
                        "system_id": "control_plane",
                        "restore_risk": True,
                        "subject_ids": [SUBJECT_USER_ID],
                        "subject_values": [CURRENT_EMAIL],
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def seed_demo(settings: Settings | None = None) -> DemoContext:
    settings = settings or get_settings()
    settings.data_dir = Path(settings.data_dir).resolve()
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    audit_at = datetime.now(timezone.utc) + timedelta(hours=1)
    demo_dir = settings.data_dir / "demo"
    app_db = demo_dir / "app.db"
    bucket_root = demo_dir / "bucket"
    control_path = demo_dir / "control.json"
    app_db.parent.mkdir(parents=True, exist_ok=True)

    _create_app_database(app_db, audit_at)
    _create_bucket(bucket_root, audit_at)
    _create_control_plane(control_path)

    database = get_database()
    database.drop_all()
    database.create_all()

    with database.session() as session:
        tenant = Tenant(
            id=TENANT_ID,
            name="Acme Commerce (demo)",
            jurisdiction="gdpr",
            created_at=utcnow(),
        )
        session.add(tenant)
        session.flush()

        subject = Subject(
            id=new_id("sub"),
            tenant_id=TENANT_ID,
            user_id=SUBJECT_USER_ID,
            created_at=utcnow(),
        )
        session.add(subject)
        session.flush()

        identifiers = [
            Identifier(
                type=IdentifierType.EMAIL,
                value=CURRENT_EMAIL,
                valid_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
                source="account",
            ),
            Identifier(
                type=IdentifierType.EMAIL,
                value=HISTORICAL_EMAIL,
                valid_from=datetime(2022, 1, 1, tzinfo=timezone.utc),
                valid_to=datetime(2024, 1, 1, tzinfo=timezone.utc),
                source="audit_log",
            ),
            Identifier(
                type=IdentifierType.PHONE,
                value=CURRENT_PHONE,
                valid_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
                source="account",
            ),
        ]
        for identifier in identifiers:
            session.add(
                IdentifierRow(
                    id=new_id("idn"),
                    subject_id=subject.id,
                    type=identifier.type.value,
                    value=identifier.value,
                    normalized=identifier.normalized(),
                    valid_from=identifier.valid_from,
                    valid_to=identifier.valid_to,
                    source=identifier.source,
                )
            )

        sql_config = {
            "system_id": "account_service",
            "url": f"sqlite:///{app_db}",
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
                },
                "search_index": {
                    "category": "SEARCH_INDEX",
                    "pk": "document_id",
                    "user_id_column": "user_id",
                    "subject_columns": [["email", "EMAIL"]],
                    "pii_fields": ["email", "display_name"],
                },
                "analytics_events": {
                    "category": "ANALYTICS",
                    "pk": "event_id",
                    "user_id_column": "user_id",
                    "subject_columns": [["email", "EMAIL"]],
                    "pii_fields": ["email"],
                },
                "support_tickets": {
                    "category": "SUPPORT",
                    "pk": "ticket_id",
                    "user_id_column": "user_id",
                    "subject_columns": [["email", "EMAIL"]],
                    "pii_fields": ["email", "body"],
                },
                "audit_trail": {
                    "category": "AUDIT_TRAIL",
                    "pk": "audit_id",
                    "user_id_column": "user_id",
                    "subject_columns": [],
                    "pii_fields": [],
                },
                "tombstones": {
                    "category": "TOMBSTONE",
                    "pk": "tombstone_id",
                    "user_id_column": "user_id",
                    "subject_columns": [["email", "EMAIL"]],
                    "pii_fields": ["name", "email", "phone", "email_hash"],
                },
            },
        }
        local_config = {
            "system_id": "object_store",
            "backend": "local",
            "root": str(bucket_root),
            "categories": {
                "exports/": "EXPORT",
                "attachments/": "SUPPORT",
                "logs/": "LOG",
            },
            "default_category": "EXPORT",
        }
        control_config = {
            "system_id": "control_plane",
            "path": str(control_path),
        }

        for type_name, name, config in (
            ("sql", "account_service", sql_config),
            ("local", "object_store", local_config),
            ("control", "control_plane", control_config),
        ):
            session.add(
                ConnectorRow(
                    id=new_id("con"),
                    tenant_id=TENANT_ID,
                    type=type_name,
                    name=name,
                    config=config,
                    enabled=True,
                    created_at=utcnow(),
                )
            )

        request = RequestRow(
            id=new_id("req"),
            tenant_id=TENANT_ID,
            subject_id=subject.id,
            email=CURRENT_EMAIL,
            request_text="Please delete my account and all of my personal data.",
            requested_at=audit_at - timedelta(days=1),
            audit_at=audit_at,
            jurisdiction="gdpr",
            status="PENDING",
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        session.add(request)
        session.flush()

        return DemoContext(
            tenant_id=TENANT_ID,
            subject_id=subject.id,
            request_id=request.id,
            audit_at=audit_at,
            app_db=app_db,
            bucket_root=bucket_root,
            control_path=control_path,
        )


def run_demo(settings: Settings | None = None) -> RunResult:
    settings = settings or get_settings()
    context = seed_demo(settings)

    store = EvidenceStore(settings.evidence_dir or settings.data_dir / "evidence")
    ledger = EvidenceLedger(settings.ledger_path or settings.data_dir / "ledger.jsonl")
    attestations = AttestationService(
        settings.attestation_key,
        settings.attestation_dir or settings.data_dir / "attestations",
    )
    policies = PolicyRegistry.load(settings.policy_dir)

    database = get_database()
    with database.session() as session:
        subject = resolve_from_db(
            session, context.tenant_id, CURRENT_EMAIL, context.audit_at
        )
        connectors = load_for_tenant(session, context.tenant_id, store)
        orchestrator = ErasureOrchestrator(
            connectors=connectors,
            policy=policies,
            evidence_store=store,
            ledger=ledger,
            attestations=attestations,
        )
        try:
            result = orchestrator.run(
                request_id=context.request_id,
                subject=subject,
                audit_at=context.audit_at,
                jurisdiction="gdpr",
                remediate=True,
            )
        finally:
            orchestrator.close()

        request = session.get(RequestRow, context.request_id)
        if request is not None:
            request.status = result.status
            request.plan = result.plan.to_dict()
            request.result = {
                "status": result.status,
                "remediation_applied": result.remediation_applied,
                "graph": result.graph.to_dict() if result.graph else None,
                "verifications": [v.to_dict() for v in result.verifications],
                "attestation": result.attestation.to_dict() if result.attestation else None,
            }
            request.updated_at = utcnow()

    return result
