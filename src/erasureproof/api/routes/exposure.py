"""Passive public exposure scanning endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...audit import record_audit
from ...config import get_settings
from ...exposure.models import ExposureTarget
from ...exposure.service import ExposureService
from ...models.db import Database, Tenant
from ..auth import Principal, require_operator
from ..deps import get_db, get_ledger, get_store
from ..schemas import ExposureScanRequest

router = APIRouter()


@router.post("/v1/exposure/scan")
def scan_exposure(
    payload: ExposureScanRequest,
    store=Depends(get_store),
    ledger=Depends(get_ledger),
    database: Database = Depends(get_db),
    principal: Principal = Depends(require_operator),
) -> dict:
    principal.ensure_tenant(payload.tenant_id)
    tenant_id = payload.tenant_id or (None if principal.tenant_wildcard else principal.tenant_id)
    if tenant_id is not None:
        with database.session() as session:
            if session.get(Tenant, tenant_id) is None:
                raise HTTPException(status_code=404, detail="tenant not found")
    settings = get_settings()
    service = ExposureService(settings, store, ledger)
    target = ExposureTarget(
        email=payload.email,
        phone=payload.phone,
        name=payload.name,
        usernames=payload.usernames,
        urls=payload.urls,
    )
    try:
        report = service.scan(
            target,
            collectors=payload.collectors,
            authorized=payload.authorized,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    with database.session() as session:
        record_audit(
            session,
            principal,
            action="exposure.scanned",
            resource_type="exposure_scan",
            resource_id=report.report_evidence_id,
            tenant_id=tenant_id,
            detail={
                "authorized": payload.authorized,
                "collectors": payload.collectors or [],
                "hits": len(report.hits),
                "errors": len(report.errors),
            },
        )
    return report.to_dict()
