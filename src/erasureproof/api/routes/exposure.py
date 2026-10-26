"""Passive public exposure scanning endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ...config import get_settings
from ...exposure.models import ExposureTarget
from ...exposure.service import ExposureService
from ..deps import get_ledger, get_store
from ..schemas import ExposureScanRequest

router = APIRouter()


@router.post("/v1/exposure/scan")
def scan_exposure(
    payload: ExposureScanRequest,
    store=Depends(get_store),
    ledger=Depends(get_ledger),
) -> dict:
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
    return report.to_dict()
