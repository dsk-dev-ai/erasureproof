"""Health, policy and ledger endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query

from ... import __version__
from ...config import get_settings
from ..deps import get_ledger, get_policies
from ..schemas import HealthOut, LedgerVerifyOut

router = APIRouter()


@router.get("/healthz", response_model=HealthOut)
def healthz() -> HealthOut:
    settings = get_settings()
    return HealthOut(
        status="ok",
        version=__version__,
        database="sqlite" if settings.is_sqlite else "postgresql",
    )


@router.get("/version")
def version() -> dict[str, str]:
    return {"name": "ErasureProof", "version": __version__}


@router.get("/v1/policies")
def list_policies() -> dict:
    registry = get_policies()
    return {
        "jurisdictions": registry.jurisdictions(),
        "policies": {j: registry.get(j).to_dict() for j in registry.jurisdictions()},
    }


@router.get("/v1/ledger")
def read_ledger(limit: int = Query(default=100, ge=1, le=1000)) -> dict:
    ledger = get_ledger()
    entries = ledger.read()
    return {
        "head": ledger.head(),
        "count": len(entries),
        "entries": [entry.to_dict() for entry in entries[-limit:]],
    }


@router.post("/v1/ledger/verify", response_model=LedgerVerifyOut)
def verify_ledger() -> LedgerVerifyOut:
    ledger = get_ledger()
    valid, detail = ledger.verify()
    return LedgerVerifyOut(valid=valid, detail=detail, head=ledger.head())
