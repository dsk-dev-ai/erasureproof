"""Health, policy and ledger endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from ... import __version__
from ...config import get_settings
from ..deps import get_ledger, get_policies, get_store
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


def _safe_evidence_id(evidence_id: str) -> str:
    if not evidence_id.startswith("ev_") or not all(
        character.isalnum() or character in {"_", "-"} for character in evidence_id
    ):
        raise HTTPException(status_code=404, detail="evidence not found")
    return evidence_id


@router.get("/v1/evidence")
def list_evidence(
    request_id: str | None = Query(default=None),
    source: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    store = get_store()
    items = []
    for path in store.meta.glob("*.json"):
        try:
            metadata = store.metadata(path.stem)
        except (FileNotFoundError, ValueError):
            continue
        if request_id and metadata.get("request_id") != request_id:
            continue
        if source and source.lower() not in str(metadata.get("source", "")).lower():
            continue
        metadata.pop("path", None)
        items.append(metadata)
    items.sort(key=lambda item: item.get("captured_at", ""), reverse=True)
    return {"count": len(items), "items": items[:limit]}


@router.get("/v1/evidence/{evidence_id}")
def get_evidence(evidence_id: str) -> dict:
    evidence_id = _safe_evidence_id(evidence_id)
    store = get_store()
    try:
        metadata = store.metadata(evidence_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="evidence not found") from exc
    metadata.pop("path", None)
    return metadata


@router.get("/v1/evidence/{evidence_id}/content")
def get_evidence_content(evidence_id: str):
    evidence_id = _safe_evidence_id(evidence_id)
    store = get_store()
    try:
        metadata = store.metadata(evidence_id)
        path = store.root / "objects" / metadata["sha256"][:2] / metadata["sha256"]
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="evidence not found") from exc
    if not path.exists():
        raise HTTPException(status_code=404, detail="evidence object missing")
    return FileResponse(
        path,
        media_type=metadata.get("content_type", "application/octet-stream"),
        filename=evidence_id,
        content_disposition_type="inline",
    )


@router.post("/v1/evidence/{evidence_id}/verify")
def verify_evidence(evidence_id: str) -> dict:
    evidence_id = _safe_evidence_id(evidence_id)
    store = get_store()
    try:
        valid = store.verify(evidence_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="evidence not found") from exc
    return {"evidence_id": evidence_id, "valid": valid}
