"""Isolated, self-service sandbox workspaces.

Each sandbox gets its own tenant, control-plane rows and connector files. The
seeded data is fictional and intentionally small so a developer can exercise the
full audit and attestation flow immediately after onboarding.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import Settings
from .demo import (
    BOB_EMAIL,
    BOB_PHONE,
    BOB_USER_ID,
    CURRENT_EMAIL,
    CURRENT_PHONE,
    HISTORICAL_EMAIL,
    SUBJECT_USER_ID,
    _create_app_database,
    _create_bucket,
    _create_control_plane,
)
from .models.db import (
    ConnectorRow,
    IdentifierRow,
    RequestRow,
    Subject,
    Tenant,
    get_database,
    new_id,
)
from .models.domain import Identifier, IdentifierType, utcnow


def create_sandbox_workspace(
    *,
    tenant_name: str,
    jurisdiction: str,
    settings: Settings,
) -> tuple[str, str, datetime]:
    """Create a tenant with seeded connectors and one audit-ready request.

    Returns ``(tenant_id, request_id, audit_at)``.
    """

    tenant_id = new_id("ten")
    request_id = new_id("req")
    audit_at = datetime.now(timezone.utc) + timedelta(hours=1)

    root = Path(settings.data_dir).resolve() / "sandboxes" / tenant_id
    app_db = root / "app.db"
    bucket_root = root / "bucket"
    control_path = root / "control.json"
    root.mkdir(parents=True, exist_ok=True)

    _create_app_database(app_db, audit_at)
    _create_bucket(bucket_root, audit_at)
    _create_control_plane(control_path)

    database = get_database()
    with database.session() as session:
        session.add(
            Tenant(
                id=tenant_id,
                name=tenant_name,
                jurisdiction=jurisdiction,
                created_at=utcnow(),
            )
        )
        session.flush()

        subject = Subject(
            id=new_id("sub"),
            tenant_id=tenant_id,
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

        decoy = Subject(
            id=new_id("sub"),
            tenant_id=tenant_id,
            user_id=BOB_USER_ID,
            created_at=utcnow(),
        )
        session.add(decoy)
        session.flush()
        for identifier in (
            Identifier(
                type=IdentifierType.EMAIL,
                value=BOB_EMAIL,
                valid_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
                source="account",
            ),
            Identifier(
                type=IdentifierType.PHONE,
                value=BOB_PHONE,
                valid_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
                source="account",
            ),
        ):
            session.add(
                IdentifierRow(
                    id=new_id("idn"),
                    subject_id=decoy.id,
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
                    tenant_id=tenant_id,
                    type=type_name,
                    name=name,
                    config=config,
                    enabled=True,
                    created_at=utcnow(),
                )
            )

        session.add(
            RequestRow(
                id=request_id,
                tenant_id=tenant_id,
                subject_id=subject.id,
                email=CURRENT_EMAIL,
                request_text="Please delete my account and all of my personal data.",
                requested_at=audit_at - timedelta(days=1),
                audit_at=audit_at,
                jurisdiction=jurisdiction,
                status="PENDING",
                created_at=utcnow(),
                updated_at=utcnow(),
            )
        )

    return tenant_id, request_id, audit_at
