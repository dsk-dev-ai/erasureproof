"""Deletion-request endpoints."""

from __future__ import annotations

from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from ...config import get_settings
from ...connectors.registry import load_for_tenant
from ...core.identity import resolve_from_db, resolve_graph
from ...core.normalize import classify_request
from ...models.db import Database, IdentifierRow, RequestRow, Subject, Tenant, new_id
from ...models.domain import (
    Identifier,
    IdentifierType,
    KnownSubject,
    Plan,
    utcnow,
)
from ...orchestrator.runner import ErasureOrchestrator, RunResult
from ..deps import (
    get_attestations,
    get_db,
    get_ledger,
    get_policies,
    get_store,
)
from ..schemas import AttestationOut, RequestCreate, RequestOut, RunResponse

router = APIRouter()

_TERMINAL = {"COMPLETE", "INCOMPLETE", "NOT_APPLICABLE"}


def _request_out(row: RequestRow) -> RequestOut:
    return RequestOut(
        id=row.id,
        tenant_id=row.tenant_id,
        email=row.email,
        status=row.status,
        request_text=row.request_text,
        requested_at=row.requested_at,
        audit_at=row.audit_at,
        jurisdiction=row.jurisdiction,
        result=row.result,
        plan=row.plan,
    )


def _run_response_from_result(result: RunResult) -> RunResponse:
    return RunResponse(**result.to_dict())


def _stored_response(row: RequestRow) -> RunResponse:
    stored = row.result or {}
    plan = row.plan or {"request_id": row.id, "status": row.status, "steps": []}
    return RunResponse(
        request_id=row.id,
        status=row.status,
        plan=plan,
        verification=stored.get("verification", stored.get("verifications", [])),
        actions=stored.get("actions", []),
        attestation=stored.get("attestation"),
        ledger_head=stored.get("ledger_head", ""),
        remediation_applied=bool(stored.get("remediation_applied", False)),
        errors=stored.get("errors", []),
    )


@router.post("/v1/requests", response_model=RequestOut, status_code=status.HTTP_201_CREATED)
def create_request(
    payload: RequestCreate, database: Database = Depends(get_db)
) -> RequestOut:
    intent = classify_request(payload.request_text)
    requested_at = payload.requested_at or utcnow()
    audit_at = payload.audit_at
    if audit_at.tzinfo is None:
        audit_at = audit_at.replace(tzinfo=timezone.utc)

    with database.session() as session:
        if session.get(Tenant, payload.tenant_id) is None:
            raise HTTPException(status_code=404, detail="tenant not found")

        row = RequestRow(
            id=new_id("req"),
            tenant_id=payload.tenant_id,
            subject_id=None,
            email=payload.email,
            request_text=payload.request_text,
            requested_at=requested_at,
            audit_at=audit_at,
            jurisdiction=payload.jurisdiction
            or session.get(Tenant, payload.tenant_id).jurisdiction,
            status="PENDING" if intent.is_deletion else "NOT_APPLICABLE",
            result=None if intent.is_deletion else {"intent": intent.to_dict()},
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        session.add(row)
        session.flush()
        return _request_out(row)


@router.get("/v1/requests/{request_id}", response_model=RequestOut)
def get_request(request_id: str, database: Database = Depends(get_db)) -> RequestOut:
    with database.session() as session:
        row = session.get(RequestRow, request_id)
        if row is None:
            raise HTTPException(status_code=404, detail="request not found")
        return _request_out(row)


@router.get("/v1/tenants/{tenant_id}/requests", response_model=list[RequestOut])
def list_requests(
    tenant_id: str, database: Database = Depends(get_db)
) -> list[RequestOut]:
    with database.session() as session:
        rows = session.scalars(
            select(RequestRow)
            .where(RequestRow.tenant_id == tenant_id)
            .order_by(RequestRow.created_at)
        ).all()
        return [_request_out(row) for row in rows]


@router.post("/v1/requests/{request_id}/run", response_model=RunResponse)
def run_request(
    request_id: str,
    remediate: bool = Query(default=True, description="Execute remediation, not just audit"),
    force: bool = Query(default=False, description="Re-run a terminal request"),
    database: Database = Depends(get_db),
) -> RunResponse:
    settings = get_settings()
    store = get_store()
    ledger = get_ledger()
    attestations = get_attestations()
    policies = get_policies()

    with database.session() as session:
        row = session.get(RequestRow, request_id)
        if row is None:
            raise HTTPException(status_code=404, detail="request not found")
        if (
            not force
            and row.status in _TERMINAL
            and row.result is not None
            and row.result.get("attestation") is not None
        ):
            return _stored_response(row)

        intent = classify_request(row.request_text)
        if not intent.is_deletion:
            plan = Plan(request_id=row.id, steps=[], status="NOT_APPLICABLE")
            head = ledger.head()
            attestation = attestations.issue(
                request_id=row.id,
                status="NOT_APPLICABLE",
                plan=plan,
                verifications=[],
                ledger_head=head,
                extra={"subject_user_id": None, "audit_at": row.audit_at.isoformat()},
            )
            ledger.append(
                "request.not_applicable",
                row.id,
                {"category": intent.category, "attestation": attestation.path},
            )
            row.status = "NOT_APPLICABLE"
            row.plan = plan.to_dict()
            row.result = {
                "status": "NOT_APPLICABLE",
                "intent": intent.to_dict(),
                "verification": [],
                "actions": [],
                "attestation": attestation.to_dict(),
                "ledger_head": ledger.head(),
                "remediation_applied": False,
                "errors": [],
            }
            row.updated_at = utcnow()
            session.flush()
            return _stored_response(row)

        subject = resolve_from_db(session, row.tenant_id, row.email, row.audit_at)
        if not subject.user_id and row.subject_id:
            subject_row = session.get(Subject, row.subject_id)
            if subject_row is not None:
                identifier_rows = session.scalars(
                    select(IdentifierRow).where(IdentifierRow.subject_id == subject_row.id)
                ).all()
                subject = resolve_graph(
                    KnownSubject(
                        user_id=subject_row.user_id,
                        identifiers=[
                            Identifier(
                                type=IdentifierType(identifier.type),
                                value=identifier.value,
                                valid_from=identifier.valid_from,
                                valid_to=identifier.valid_to,
                                source=identifier.source,
                            )
                            for identifier in identifier_rows
                        ],
                    ),
                    row.email,
                    row.audit_at,
                )
                row.subject_id = subject_row.id

        connectors = load_for_tenant(session, row.tenant_id, store)
        orchestrator = ErasureOrchestrator(
            connectors=connectors,
            policy=policies,
            evidence_store=store,
            ledger=ledger,
            attestations=attestations,
        )
        try:
            result = orchestrator.run(
                request_id=row.id,
                subject=subject,
                audit_at=row.audit_at,
                jurisdiction=row.jurisdiction or settings.default_jurisdiction,
                remediate=remediate,
                extra={"tenant_id": row.tenant_id},
            )
        finally:
            orchestrator.close()

        row.status = result.status
        row.plan = result.plan.to_dict()
        row.result = result.to_dict()
        row.updated_at = utcnow()
        session.flush()
        return _run_response_from_result(result)


@router.get("/v1/requests/{request_id}/attestation", response_model=AttestationOut)
def get_attestation(
    request_id: str, database: Database = Depends(get_db)
) -> AttestationOut:
    with database.session() as session:
        row = session.get(RequestRow, request_id)
        if row is None:
            raise HTTPException(status_code=404, detail="request not found")
        stored = (row.result or {}).get("attestation")
        if not stored:
            raise HTTPException(status_code=404, detail="attestation not issued")
        return AttestationOut(
            request_id=stored["request_id"],
            status=stored["status"],
            signature=stored["signature"],
            path=stored["path"],
            payload=stored["payload"],
        )
