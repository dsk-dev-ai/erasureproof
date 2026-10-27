"""Audit trail and remediation approval helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .api.auth import Principal
from .models.db import ApprovalRow, AuditEventRow, RequestRow, new_id
from .models.domain import utcnow

APPROVAL_ACTIVE = {"APPROVED"}
APPROVAL_ALL = {"APPROVED", "REJECTED", "SUPERSEDED"}


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def record_audit(
    session: Session,
    principal: Principal,
    *,
    action: str,
    resource_type: str,
    resource_id: str,
    tenant_id: str | None = None,
    request_id: str | None = None,
    detail: dict | None = None,
) -> AuditEventRow:
    row = AuditEventRow(
        id=new_id("aud"),
        tenant_id=tenant_id,
        actor=principal.subject,
        actor_role=principal.role,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        request_id=request_id,
        detail=detail or {},
        created_at=utcnow(),
    )
    session.add(row)
    return row


def latest_approval(
    session: Session, request_id: str, *, for_update: bool = False
) -> ApprovalRow | None:
    statement = (
        select(ApprovalRow)
        .where(ApprovalRow.request_id == request_id)
        .order_by(ApprovalRow.created_at.desc())
        .limit(1)
    )
    if for_update:
        statement = statement.with_for_update()
    return session.scalars(statement).first()


def approval_is_active(approval: ApprovalRow | None, now: datetime | None = None) -> bool:
    if approval is None or approval.status not in APPROVAL_ACTIVE:
        return False
    if approval.consumed_at is not None:
        return False
    expires = _aware(approval.expires_at)
    return bool(expires and expires > (now or utcnow()))


def approval_to_dict(approval: ApprovalRow | None) -> dict:
    if approval is None:
        return {
            "approval_status": None,
            "approval_expires_at": None,
            "approval_consumed_at": None,
            "approved_by": None,
        }
    return {
        "approval_status": approval.status,
        "approval_expires_at": _aware(approval.expires_at),
        "approval_consumed_at": _aware(approval.consumed_at),
        "approved_by": approval.decided_by,
    }


def approval_detail(approval: ApprovalRow) -> dict:
    return {
        "id": approval.id,
        "request_id": approval.request_id,
        "tenant_id": approval.tenant_id,
        "status": approval.status,
        "requested_by": approval.requested_by,
        "decided_by": approval.decided_by,
        "reason": approval.reason,
        "created_at": _aware(approval.created_at),
        "decided_at": _aware(approval.decided_at),
        "expires_at": _aware(approval.expires_at),
        "consumed_at": _aware(approval.consumed_at),
    }


def audit_detail(row: AuditEventRow) -> dict:
    return {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "actor": row.actor,
        "actor_role": row.actor_role,
        "action": row.action,
        "resource_type": row.resource_type,
        "resource_id": row.resource_id,
        "request_id": row.request_id,
        "detail": row.detail or {},
        "created_at": _aware(row.created_at),
    }


def request_creator(session: Session, request_id: str) -> str | None:
    row = session.scalars(
        select(AuditEventRow)
        .where(
            AuditEventRow.request_id == request_id,
            AuditEventRow.action == "request.created",
        )
        .order_by(AuditEventRow.created_at)
        .limit(1)
    ).first()
    return row.actor if row is not None else None


def attach_approvals(session: Session, rows: list[RequestRow]) -> dict[str, ApprovalRow | None]:
    if not rows:
        return {}
    ids = [row.id for row in rows]
    approvals = session.scalars(
        select(ApprovalRow).where(ApprovalRow.request_id.in_(ids)).order_by(ApprovalRow.created_at)
    ).all()
    result: dict[str, ApprovalRow | None] = {row_id: None for row_id in ids}
    for approval in approvals:
        result[approval.request_id] = approval
    return result
