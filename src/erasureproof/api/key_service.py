"""Database-backed API key issuance helpers."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from ..api.auth import api_key_prefix, generate_api_key, hash_api_key
from ..models.db import ApiKeyRow, new_id
from ..models.domain import utcnow


def issue_api_key(
    session: Session,
    *,
    tenant_id: str,
    name: str,
    role: str,
    subject: str,
    created_by: str,
    expires_at: datetime | None,
) -> tuple[ApiKeyRow, str]:
    """Persist only a hash; return the plaintext key exactly once."""

    token = generate_api_key()
    row = ApiKeyRow(
        id=new_id("key"),
        tenant_id=tenant_id,
        name=name,
        key_prefix=api_key_prefix(token),
        key_hash=hash_api_key(token),
        role=role,
        subject=subject,
        created_by=created_by,
        created_at=utcnow(),
        expires_at=expires_at,
    )
    session.add(row)
    session.flush()
    return row, token
