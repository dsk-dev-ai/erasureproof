"""Approval workflow and tamper-evident operational audit endpoints."""

from __future__ import annotations

import csv
import io
import json
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import or_, select, update

from ...audit import (
    approval_detail,
    audit_detail,
    record_audit,
    request_creator,
)
from ...config import get_settings
from ...models.db import ApprovalRow, AuditEventRow, Database, RequestRow, new_id
from ...models.domain import utcnow
from ..auth import Principal, require_admin, require_viewer
from ..deps import get_db
from ..schemas import ApprovalDecision, ApprovalOut, AuditEventOut

router = APIRouter()


def _csv_cell(value: object) -> str:
    text = "" if value is None else str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + text
    return text


def _request_or_404(session, request_id: str) -> RequestRow:
    row = session.get(RequestRow, request_id)
    if row is None:
        raise HTTPException(status_code=404, detail="request not found")
    return row


@router.post(
    "/v1/requests/{request_id}/approval",
    response_model=ApprovalOut,
    status_code=201,
)
def decide_approval(
    request_id: str,
    payload: ApprovalDecision,
    database: Database = Depends(get_db),
    principal: Principal = Depends(require_admin),
) -> ApprovalOut:
    settings = get_settings()
    with database.session() as session:
        row = _request_or_404(session, request_id)
        principal.ensure_tenant(row.tenant_id)
        if row.status == "NOT_APPLICABLE":
            raise HTTPException(status_code=409, detail="request does not authorize deletion")

        creator = request_creator(session, request_id)
        if (
            payload.decision == "APPROVED"
            and settings.approval_requires_separate_user
            and creator is not None
            and creator == principal.subject
        ):
            raise HTTPException(
                status_code=409,
                detail="remediation must be approved by a different administrator",
            )

        session.execute(
            update(ApprovalRow)
            .where(
                ApprovalRow.request_id == request_id,
                ApprovalRow.status == "APPROVED",
                ApprovalRow.consumed_at.is_(None),
            )
            .values(status="SUPERSEDED")
        )
        now = utcnow()
        approval = ApprovalRow(
            id=new_id("apr"),
            request_id=request_id,
            tenant_id=row.tenant_id,
            status=payload.decision,
            requested_by=creator or "unknown",
            decided_by=principal.subject,
            reason=payload.reason.strip(),
            created_at=now,
            decided_at=now,
            expires_at=(
                now + timedelta(hours=settings.approval_ttl_hours)
                if payload.decision == "APPROVED"
                else None
            ),
        )
        session.add(approval)
        record_audit(
            session,
            principal,
            action=f"approval.{payload.decision.lower()}",
            resource_type="request",
            resource_id=request_id,
            tenant_id=row.tenant_id,
            request_id=request_id,
            detail={"approval_id": approval.id, "reason": approval.reason},
        )
        session.flush()
        return ApprovalOut(**approval_detail(approval))


@router.get("/v1/requests/{request_id}/approvals", response_model=list[ApprovalOut])
def list_approvals(
    request_id: str,
    database: Database = Depends(get_db),
    principal: Principal = Depends(require_viewer),
) -> list[ApprovalOut]:
    with database.session() as session:
        row = _request_or_404(session, request_id)
        principal.ensure_tenant(row.tenant_id)
        approvals = session.scalars(
            select(ApprovalRow)
            .where(ApprovalRow.request_id == request_id)
            .order_by(ApprovalRow.created_at.desc())
        ).all()
        return [ApprovalOut(**approval_detail(item)) for item in approvals]


@router.get("/v1/approvals/active", response_model=list[ApprovalOut])
def pending_approvals(
    tenant_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    database: Database = Depends(get_db),
    principal: Principal = Depends(require_viewer),
) -> list[ApprovalOut]:
    principal.ensure_tenant(tenant_id)
    scoped_tenant = tenant_id or (None if principal.tenant_wildcard else principal.tenant_id)
    now = utcnow()
    filters = [
        ApprovalRow.status == "APPROVED",
        ApprovalRow.consumed_at.is_(None),
        or_(ApprovalRow.expires_at.is_(None), ApprovalRow.expires_at > now),
    ]
    if scoped_tenant:
        filters.append(ApprovalRow.tenant_id == scoped_tenant)
    with database.session() as session:
        approvals = session.scalars(
            select(ApprovalRow).where(*filters).order_by(ApprovalRow.created_at.desc()).limit(limit)
        ).all()
        return [ApprovalOut(**approval_detail(item)) for item in approvals]


@router.get("/v1/audit-events", response_model=list[AuditEventOut])
def list_audit_events(
    tenant_id: str | None = Query(default=None),
    action: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    database: Database = Depends(get_db),
    principal: Principal = Depends(require_admin),
) -> list[AuditEventOut]:
    principal.ensure_tenant(tenant_id)
    scoped_tenant = tenant_id or (None if principal.tenant_wildcard else principal.tenant_id)
    filters = []
    if scoped_tenant:
        filters.append(AuditEventRow.tenant_id == scoped_tenant)
    if action:
        filters.append(AuditEventRow.action == action)
    with database.session() as session:
        rows = session.scalars(
            select(AuditEventRow)
            .where(*filters)
            .order_by(AuditEventRow.created_at.desc())
            .limit(limit)
        ).all()
        return [AuditEventOut(**audit_detail(row)) for row in rows]


@router.get("/v1/audit-events/export")
def export_audit_events(
    tenant_id: str | None = Query(default=None),
    limit: int = Query(default=5000, ge=1, le=50000),
    database: Database = Depends(get_db),
    principal: Principal = Depends(require_admin),
) -> Response:
    principal.ensure_tenant(tenant_id)
    scoped_tenant = tenant_id or (None if principal.tenant_wildcard else principal.tenant_id)
    filters = [AuditEventRow.tenant_id == scoped_tenant] if scoped_tenant else []
    with database.session() as session:
        rows = session.scalars(
            select(AuditEventRow).where(*filters).order_by(AuditEventRow.created_at).limit(limit)
        ).all()
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "created_at",
                "tenant_id",
                "actor",
                "actor_role",
                "action",
                "resource_type",
                "resource_id",
                "request_id",
                "detail",
            ]
        )
        for row in rows:
            item = audit_detail(row)
            writer.writerow(
                [
                    item["created_at"].isoformat() if item["created_at"] else "",
                    item["tenant_id"] or "",
                    _csv_cell(item["actor"]),
                    _csv_cell(item["actor_role"]),
                    _csv_cell(item["action"]),
                    _csv_cell(item["resource_type"]),
                    _csv_cell(item["resource_id"]),
                    item["request_id"] or "",
                    _csv_cell(json.dumps(item["detail"], sort_keys=True, separators=(",", ":"))),
                ]
            )
    filename = f"erasureproof-audit-{utcnow().strftime('%Y%m%dT%H%M%SZ')}.csv"
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
