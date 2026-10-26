"""Subject and identifier endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from ...models.db import Database, IdentifierRow, Subject, Tenant, new_id
from ...models.domain import IdentifierType, normalize_value, utcnow
from ..deps import get_db
from ..schemas import IdentifierIn, SubjectCreate, SubjectOut

router = APIRouter()


def _to_out(subject: Subject, identifiers: list[IdentifierRow]) -> SubjectOut:
    return SubjectOut(
        id=subject.id,
        tenant_id=subject.tenant_id,
        user_id=subject.user_id,
        identifiers=[
            IdentifierIn(
                type=IdentifierType(row.type),
                value=row.value,
                valid_from=row.valid_from,
                valid_to=row.valid_to,
                source=row.source,
            )
            for row in identifiers
        ],
        created_at=subject.created_at,
    )


@router.post("/v1/subjects", response_model=SubjectOut, status_code=status.HTTP_201_CREATED)
def create_subject(payload: SubjectCreate, database: Database = Depends(get_db)) -> SubjectOut:
    with database.session() as session:
        if session.get(Tenant, payload.tenant_id) is None:
            raise HTTPException(status_code=404, detail="tenant not found")

        subject = Subject(
            id=new_id("sub"),
            tenant_id=payload.tenant_id,
            user_id=payload.user_id,
            created_at=utcnow(),
        )
        session.add(subject)
        session.flush()

        rows = []
        for identifier in payload.identifiers:
            row = IdentifierRow(
                id=new_id("idn"),
                subject_id=subject.id,
                type=identifier.type.value,
                value=identifier.value,
                normalized=normalize_value(identifier.value, identifier.type),
                valid_from=identifier.valid_from,
                valid_to=identifier.valid_to,
                source=identifier.source,
            )
            session.add(row)
            rows.append(row)
        session.flush()
        return _to_out(subject, rows)


@router.get("/v1/tenants/{tenant_id}/subjects", response_model=list[SubjectOut])
def list_subjects(tenant_id: str, database: Database = Depends(get_db)) -> list[SubjectOut]:
    with database.session() as session:
        subjects = session.scalars(
            select(Subject).where(Subject.tenant_id == tenant_id).order_by(Subject.created_at)
        ).all()
        result = []
        for subject in subjects:
            identifiers = session.scalars(
                select(IdentifierRow).where(IdentifierRow.subject_id == subject.id)
            ).all()
            result.append(_to_out(subject, list(identifiers)))
        return result


@router.get("/v1/subjects/{subject_id}", response_model=SubjectOut)
def get_subject(subject_id: str, database: Database = Depends(get_db)) -> SubjectOut:
    with database.session() as session:
        subject = session.get(Subject, subject_id)
        if subject is None:
            raise HTTPException(status_code=404, detail="subject not found")
        identifiers = session.scalars(
            select(IdentifierRow).where(IdentifierRow.subject_id == subject.id)
        ).all()
        return _to_out(subject, list(identifiers))
