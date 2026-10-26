"""Identity resolution.

A deletion must cover every identifier a person has used, not just the email in
the request. The resolver reunites current and historical identifiers (email,
phone, email hash) into a single subject graph.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.db import IdentifierRow, Subject
from ..models.domain import (
    Identifier,
    IdentifierType,
    KnownSubject,
    SubjectGraph,
    hash_email,
    normalize_value,
)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def resolve_graph(
    known: KnownSubject,
    request_email: str,
    as_of: datetime | None = None,
    matched_by: str = "identity_store",
) -> SubjectGraph:
    """Build a subject graph from known identifiers plus the request email."""

    identifiers: list[Identifier] = []
    seen: set[tuple[IdentifierType, str]] = set()

    for identifier in known.identifiers:
        valid_from = _aware(identifier.valid_from)
        if as_of is not None and valid_from is not None and valid_from > as_of:
            continue
        key = (identifier.type, identifier.normalized())
        if key in seen:
            continue
        seen.add(key)
        identifiers.append(identifier)

    if request_email:
        email_key = (IdentifierType.EMAIL, normalize_value(request_email, IdentifierType.EMAIL))
        if email_key not in seen:
            identifiers.append(
                Identifier(
                    type=IdentifierType.EMAIL,
                    value=request_email,
                    source="request",
                )
            )

    for identifier in list(identifiers):
        if identifier.type is not IdentifierType.EMAIL:
            continue
        digest = hash_email(identifier.value)
        hash_key = (IdentifierType.EMAIL_HASH, normalize_value(digest, IdentifierType.EMAIL_HASH))
        if hash_key in seen:
            continue
        seen.add(hash_key)
        identifiers.append(
            Identifier(type=IdentifierType.EMAIL_HASH, value=digest, source="derived")
        )

    return SubjectGraph(
        user_id=known.user_id,
        identifiers=identifiers,
        matched_by=matched_by,
    )


def resolve_from_db(
    session: Session,
    tenant_id: str,
    email: str,
    as_of: datetime | None = None,
) -> SubjectGraph:
    """Resolve a request email to a subject and all of its identifiers."""

    as_of = _aware(as_of)
    normalized = normalize_value(email, IdentifierType.EMAIL)

    matched_rows = session.scalars(
        select(IdentifierRow)
        .join(Subject, Subject.id == IdentifierRow.subject_id)
        .where(
            Subject.tenant_id == tenant_id,
            IdentifierRow.normalized == normalized,
            IdentifierRow.type == IdentifierType.EMAIL.value,
        )
    ).all()

    if not matched_rows:
        matched_rows = session.scalars(
            select(IdentifierRow)
            .join(Subject, Subject.id == IdentifierRow.subject_id)
            .where(
                Subject.tenant_id == tenant_id,
                IdentifierRow.normalized == hash_email(email),
                IdentifierRow.type == IdentifierType.EMAIL_HASH.value,
            )
        ).all()

    if not matched_rows:
        return resolve_graph(
            KnownSubject(user_id="", identifiers=[]),
            email,
            as_of,
            matched_by="request_only",
        )

    subject = session.get(Subject, matched_rows[0].subject_id)
    if subject is None:
        return resolve_graph(
            KnownSubject(user_id="", identifiers=[]),
            email,
            as_of,
            matched_by="request_only",
        )

    rows = session.scalars(
        select(IdentifierRow).where(IdentifierRow.subject_id == subject.id)
    ).all()

    identifiers = [
        Identifier(
            type=IdentifierType(row.type),
            value=row.value,
            valid_from=_aware(row.valid_from),
            valid_to=_aware(row.valid_to),
            source=row.source,
        )
        for row in rows
    ]

    graph = resolve_graph(
        KnownSubject(user_id=subject.user_id, identifiers=identifiers),
        email,
        as_of,
        matched_by="identity_store",
    )

    current = any(
        _aware(row.valid_to) is None for row in rows if row.normalized == normalized
    )
    graph.confidence = 1.0 if current else 0.9
    return graph


def identifiers_at(graph: SubjectGraph, as_of: datetime | None) -> list[Identifier]:
    return [i for i in graph.identifiers if i.is_valid_at(as_of)]
