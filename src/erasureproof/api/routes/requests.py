"""Deletion-request endpoints."""

from __future__ import annotations

from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import or_, select, update

from ...audit import (
    approval_is_active,
    approval_to_dict,
    attach_approvals,
    latest_approval,
    record_audit,
)
from ...config import get_settings
from ...connectors.registry import load_for_tenant
from ...core.graph import build_step_graph, plan_from_dict
from ...core.identity import resolve_from_db, resolve_graph
from ...core.normalize import classify_request
from ...models.db import (
    ApprovalRow,
    Database,
    IdentifierRow,
    RequestRow,
    Subject,
    Tenant,
    new_id,
)
from ...models.domain import (
    Identifier,
    IdentifierType,
    KnownSubject,
    Plan,
    utcnow,
)
from ...orchestrator.runner import ErasureOrchestrator, RunResult
from ..auth import Principal, require_operator, require_viewer
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


def _request_out(row: RequestRow, approval: ApprovalRow | None = None) -> RequestOut:
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
        **approval_to_dict(approval),
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
        graph=stored.get("graph"),
        verification=stored.get("verification", stored.get("verifications", [])),
        actions=stored.get("actions", []),
        attestation=stored.get("attestation"),
        ledger_head=stored.get("ledger_head", ""),
        remediation_applied=bool(stored.get("remediation_applied", False)),
        errors=stored.get("errors", []),
    )


@router.post("/v1/requests", response_model=RequestOut, status_code=status.HTTP_201_CREATED)
def create_request(
    payload: RequestCreate,
    database: Database = Depends(get_db),
    principal: Principal = Depends(require_operator),
) -> RequestOut:
    principal.ensure_tenant(payload.tenant_id)
    intent = classify_request(payload.request_text)
    requested_at = payload.requested_at or utcnow()
    audit_at = payload.audit_at
    if audit_at.tzinfo is None:
        audit_at = audit_at.replace(tzinfo=timezone.utc)

    with database.session() as session:
        tenant = session.get(Tenant, payload.tenant_id)
        if tenant is None:
            raise HTTPException(status_code=404, detail="tenant not found")

        row = RequestRow(
            id=new_id("req"),
            tenant_id=payload.tenant_id,
            subject_id=None,
            email=payload.email,
            request_text=payload.request_text,
            requested_at=requested_at,
            audit_at=audit_at,
            jurisdiction=payload.jurisdiction or tenant.jurisdiction,
            status="PENDING" if intent.is_deletion else "NOT_APPLICABLE",
            result=None if intent.is_deletion else {"intent": intent.to_dict()},
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        session.add(row)
        session.flush()
        record_audit(
            session,
            principal,
            action="request.created",
            resource_type="request",
            resource_id=row.id,
            tenant_id=row.tenant_id,
            request_id=row.id,
            detail={
                "jurisdiction": row.jurisdiction,
                "deletion_intent": intent.is_deletion,
                "intent_category": intent.category,
            },
        )
        return _request_out(row)


@router.get("/v1/requests", response_model=list[RequestOut])
def list_all_requests(
    tenant_id: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    database: Database = Depends(get_db),
    principal: Principal = Depends(require_viewer),
) -> list[RequestOut]:
    principal.ensure_tenant(tenant_id)
    if tenant_id is None and not principal.tenant_wildcard:
        tenant_id = principal.tenant_id
    filters = []
    if tenant_id:
        filters.append(RequestRow.tenant_id == tenant_id)
    if status_filter:
        filters.append(RequestRow.status == status_filter.upper())
    with database.session() as session:
        rows = session.scalars(
            select(RequestRow).where(*filters).order_by(RequestRow.created_at.desc()).limit(limit)
        ).all()
        approvals = attach_approvals(session, list(rows))
        return [_request_out(row, approvals.get(row.id)) for row in rows]


@router.get("/v1/requests/{request_id}", response_model=RequestOut)
def get_request(
    request_id: str,
    database: Database = Depends(get_db),
    principal: Principal = Depends(require_viewer),
) -> RequestOut:
    with database.session() as session:
        row = session.get(RequestRow, request_id)
        if row is None:
            raise HTTPException(status_code=404, detail="request not found")
        principal.ensure_tenant(row.tenant_id)
        return _request_out(row, latest_approval(session, request_id))


@router.get("/v1/tenants/{tenant_id}/requests", response_model=list[RequestOut])
def list_requests(
    tenant_id: str,
    database: Database = Depends(get_db),
    principal: Principal = Depends(require_viewer),
) -> list[RequestOut]:
    principal.ensure_tenant(tenant_id)
    with database.session() as session:
        rows = session.scalars(
            select(RequestRow)
            .where(RequestRow.tenant_id == tenant_id)
            .order_by(RequestRow.created_at)
        ).all()
        approvals = attach_approvals(session, list(rows))
        return [_request_out(row, approvals.get(row.id)) for row in rows]


@router.post("/v1/requests/{request_id}/run", response_model=RunResponse)
def run_request(
    request_id: str,
    remediate: bool = Query(default=True, description="Execute remediation, not just audit"),
    force: bool = Query(default=False, description="Re-run a terminal request"),
    database: Database = Depends(get_db),
    principal: Principal = Depends(require_operator),
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
        principal.ensure_tenant(row.tenant_id)
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
            record_audit(
                session,
                principal,
                action="request.run",
                resource_type="request",
                resource_id=row.id,
                tenant_id=row.tenant_id,
                request_id=row.id,
                detail={
                    "status": row.status,
                    "remediate": remediate,
                    "force": force,
                    "approval_id": None,
                },
            )
            session.flush()
            return _stored_response(row)

        approval: ApprovalRow | None = None
        if remediate and settings.require_remediation_approval:
            approval = latest_approval(session, row.id, for_update=True)
            claimed_at = utcnow()
            claimed = (
                session.execute(
                    update(ApprovalRow)
                    .where(
                        ApprovalRow.id == approval.id if approval else False,
                        ApprovalRow.status == "APPROVED",
                        ApprovalRow.consumed_at.is_(None),
                        or_(
                            ApprovalRow.expires_at.is_(None),
                            ApprovalRow.expires_at > claimed_at,
                        ),
                    )
                    .values(consumed_at=claimed_at)
                    .execution_options(synchronize_session=False)
                ).rowcount
                if approval is not None and approval_is_active(approval)
                else 0
            )
            if claimed != 1:
                raise HTTPException(
                    status_code=428,
                    detail=(
                        "remediation approval required; an administrator must approve "
                        "the request before destructive actions can run"
                    ),
                )
            record_audit(
                session,
                principal,
                action="approval.consumed",
                resource_type="approval",
                resource_id=approval.id,
                tenant_id=row.tenant_id,
                request_id=row.id,
                detail={"approval_id": approval.id},
            )

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
        record_audit(
            session,
            principal,
            action="request.run",
            resource_type="request",
            resource_id=row.id,
            tenant_id=row.tenant_id,
            request_id=row.id,
            detail={
                "status": result.status,
                "remediate": remediate,
                "force": force,
                "approval_id": approval.id if approval else None,
                "actions": len(result.actions),
                "verifications": len(result.verifications),
            },
        )
        session.flush()
        return _run_response_from_result(result)


@router.get("/v1/requests/{request_id}/attestation", response_model=AttestationOut)
def get_attestation(
    request_id: str,
    database: Database = Depends(get_db),
    principal: Principal = Depends(require_viewer),
) -> AttestationOut:
    with database.session() as session:
        row = session.get(RequestRow, request_id)
        if row is None:
            raise HTTPException(status_code=404, detail="request not found")
        principal.ensure_tenant(row.tenant_id)
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


@router.get("/v1/requests/{request_id}/graph")
def get_request_graph(
    request_id: str,
    format: str = Query(default="json", pattern="^(json|mermaid|dot)$"),
    database: Database = Depends(get_db),
    principal: Principal = Depends(require_viewer),
):
    with database.session() as session:
        row = session.get(RequestRow, request_id)
        if row is None:
            raise HTTPException(status_code=404, detail="request not found")
        principal.ensure_tenant(row.tenant_id)
        if not row.plan:
            raise HTTPException(status_code=404, detail="request has no plan yet")
        plan_data = dict(row.plan)
        stored_graph = (row.result or {}).get("graph") or {}
        categories = {
            int(node["step_no"]): node.get("category")
            for node in stored_graph.get("nodes", [])
            if node.get("category") and str(node.get("step_no", "")).isdigit()
        }
        if categories:
            plan_data["steps"] = [
                {**step, "category": categories.get(int(step.get("step_no", -1)))}
                for step in plan_data.get("steps", [])
            ]
        plan = plan_from_dict(plan_data)
        graph = build_step_graph(plan)
        if format == "mermaid":
            return PlainTextResponse(graph.to_mermaid(), media_type="text/plain")
        if format == "dot":
            return PlainTextResponse(graph.to_dot(), media_type="text/plain")
        return graph.to_dict()
