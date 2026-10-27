"""Console overview endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from ...config import get_settings
from ...demo import bootstrap_demo
from ...models.db import (
    ConnectorRow,
    Database,
    RequestRow,
    Subject,
)
from ...models.domain import Phase
from ..auth import Principal, require_operator, require_viewer
from ..deps import get_db, get_ledger, get_policies, get_store

router = APIRouter()

_STATUSES = ("PENDING", "COMPLETE", "INCOMPLETE", "NOT_APPLICABLE")


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _allowed_request_ids(
    database: Database, tenant_id: str | None, principal: Principal
) -> set[str] | None:
    if principal.tenant_wildcard:
        return None
    scoped = tenant_id or principal.tenant_id
    if scoped is None:
        return set()
    with database.session() as session:
        return set(
            session.scalars(select(RequestRow.id).where(RequestRow.tenant_id == scoped)).all()
        )


def _request_summary(row: RequestRow) -> dict:
    result = row.result or {}
    plan = row.plan or {}
    findings = sum(1 for step in plan.get("steps", []) if step.get("phase") == Phase.FINDING.value)
    verifications = result.get("verification") or result.get("verifications") or []
    passed = sum(1 for item in verifications if item.get("passed"))
    return {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "email": row.email,
        "status": row.status,
        "request_text": row.request_text,
        "requested_at": _iso(row.requested_at),
        "audit_at": _iso(row.audit_at),
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
        "jurisdiction": row.jurisdiction,
        "findings": findings,
        "verifications": len(verifications),
        "verifications_passed": passed,
        "remediation_applied": bool(result.get("remediation_applied")),
    }


@router.get("/v1/overview")
def overview(
    tenant_id: str | None = Query(default=None),
    database: Database = Depends(get_db),
    principal: Principal = Depends(require_viewer),
) -> dict:
    principal.ensure_tenant(tenant_id)
    if tenant_id is None and not principal.tenant_wildcard:
        tenant_id = principal.tenant_id
    filters = [RequestRow.tenant_id == tenant_id] if tenant_id else []
    with database.session() as session:
        total_requests = (
            session.scalar(select(func.count()).select_from(RequestRow).where(*filters)) or 0
        )
        status_rows = session.execute(
            select(RequestRow.status, func.count()).where(*filters).group_by(RequestRow.status)
        ).all()
        statuses = {status: 0 for status in _STATUSES}
        statuses.update({str(status): count for status, count in status_rows})

        subject_filters = [Subject.tenant_id == tenant_id] if tenant_id else []
        total_subjects = (
            session.scalar(select(func.count()).select_from(Subject).where(*subject_filters)) or 0
        )
        connector_filters = [ConnectorRow.tenant_id == tenant_id] if tenant_id else []
        total_connectors = (
            session.scalar(select(func.count()).select_from(ConnectorRow).where(*connector_filters))
            or 0
        )

        all_requests = session.scalars(select(RequestRow).where(*filters)).all()
        total_attestations = sum(
            1 for request in all_requests if (request.result or {}).get("attestation") is not None
        )

        rows = session.scalars(
            select(RequestRow).where(*filters).order_by(RequestRow.created_at.desc()).limit(60)
        ).all()
        recent = [_request_summary(row) for row in rows[:10]]

        verification_total = 0
        verification_passed = 0
        open_findings = 0
        for row in rows:
            result = row.result or {}
            checks = result.get("verification") or result.get("verifications") or []
            verification_total += len(checks)
            verification_passed += sum(1 for check in checks if check.get("passed"))
            if row.status in {"INCOMPLETE", "PENDING"}:
                open_findings += _request_summary(row)["findings"]

    settings = get_settings()
    store = get_store()
    allowed = _allowed_request_ids(database, tenant_id, principal)
    evidence_count = 0
    for path in store.meta.glob("*.json"):
        try:
            metadata = store.metadata(path.stem)
        except (FileNotFoundError, ValueError):
            continue
        if allowed is None or metadata.get("request_id") in allowed:
            evidence_count += 1
    ledger = get_ledger()
    ledger_entries = ledger.read()
    if allowed is not None:
        ledger_entries = [
            entry for entry in ledger_entries if entry.request_id and entry.request_id in allowed
        ]
    policies = get_policies()

    today = datetime.now(timezone.utc).date()
    days = [today - timedelta(days=offset) for offset in range(13, -1, -1)]
    trend_counts = {day.isoformat(): 0 for day in days}
    for row in rows:
        created = row.created_at
        if created is None:
            continue
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        key = created.date().isoformat()
        if key in trend_counts:
            trend_counts[key] += 1

    incomplete = statuses.get("INCOMPLETE", 0)
    pending = statuses.get("PENDING", 0)
    attestation_ratio = (
        round(total_attestations / total_requests * 100, 1) if total_requests else 0.0
    )

    return {
        "tenant_id": tenant_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "totals": {
            "requests": total_requests,
            "subjects": total_subjects,
            "connectors": total_connectors,
            "evidence": evidence_count,
            "attestations": total_attestations,
            "ledger_entries": len(ledger_entries),
        },
        "statuses": statuses,
        "verification": {
            "checks": verification_total,
            "passed": verification_passed,
            "pass_rate": round(verification_passed / verification_total * 100, 1)
            if verification_total
            else 0.0,
        },
        "attestation_coverage": attestation_ratio,
        "open_findings": open_findings,
        "risk_score": min(100, incomplete * 14 + pending * 5 + open_findings // 3),
        "recent_requests": recent,
        "trend": [{"date": day, "count": trend_counts[day]} for day in sorted(trend_counts)],
        "ledger": {
            "head": ledger.head(),
            "recent": [entry.to_dict() for entry in ledger_entries[-8:]],
        },
        "policies": policies.jurisdictions(),
        "features": {
            "exposure_enabled": settings.exposure_enabled,
            "demo_enabled": settings.demo_enabled,
            "environment": settings.environment,
            "auth_mode": settings.auth_mode.lower(),
            "approval_required": settings.require_remediation_approval,
        },
    }


@router.post("/v1/demo/seed")
def seed_demo_workspace(principal: Principal = Depends(require_operator)) -> dict:
    settings = get_settings()
    if not settings.demo_enabled:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="demo workspace is disabled",
        )
    principal.ensure_tenant("ten_demo")
    return bootstrap_demo(settings)
