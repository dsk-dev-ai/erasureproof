"""Health, policy and ledger endpoints."""

from __future__ import annotations

import hmac
import os
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from sqlalchemy import inspect, select, text

from ... import __version__
from ...config import get_settings, validate_runtime_settings
from ...middleware import render_metrics
from ...models.db import Database, RequestRow
from ..auth import Principal, authenticate, require_viewer
from ..deps import get_db, get_ledger, get_policies, get_store
from ..schemas import HealthOut, LedgerVerifyOut, ReadinessOut

router = APIRouter()


def _database_label() -> str:
    return "sqlite" if get_settings().is_sqlite else "postgresql"


@router.get("/healthz", response_model=HealthOut)
def healthz() -> HealthOut:
    return HealthOut(status="ok", version=__version__, database=_database_label())


@router.get("/livez", include_in_schema=False)
def livez() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@router.get("/readyz", response_model=ReadinessOut)
def readyz(database: Database = Depends(get_db)) -> ReadinessOut | JSONResponse:
    checks: dict[str, str] = {}
    required_tables = {
        "tenants",
        "subjects",
        "identifiers",
        "connectors",
        "requests",
        "approvals",
        "audit_events",
        "api_keys",
    }
    try:
        with database.session() as session:
            session.execute(text("SELECT 1"))
            tables = set(inspect(session.bind).get_table_names())
        checks["database"] = "ok"
        checks["schema"] = "ok" if required_tables <= tables else "missing tables"
    except Exception:
        checks["database"] = "failed"
        checks["schema"] = "failed"

    settings = get_settings()
    for name, directory in (
        ("evidence", settings.evidence_dir),
        ("attestations", settings.attestation_dir),
    ):
        try:
            path = Path(directory or "")
            if not path.exists():
                checks[name] = "missing"
            else:
                checks[name] = "ok" if os.access(path, os.W_OK) else "read-only"
        except OSError:
            checks[name] = "failed"
    try:
        ledger_path = Path(settings.ledger_path or "")
        writable = ledger_path.parent.exists() and os.access(ledger_path.parent, os.W_OK)
        if ledger_path.exists():
            writable = writable and os.access(ledger_path, os.W_OK)
        checks["ledger"] = "ok" if writable else "failed"
    except OSError:
        checks["ledger"] = "failed"
    try:
        checks["policies"] = "ok" if get_policies().jurisdictions() else "failed"
    except Exception:
        checks["policies"] = "failed"
    try:
        validate_runtime_settings(settings)
        checks["configuration"] = "ok"
    except ValueError:
        checks["configuration"] = "failed"

    if any(value != "ok" for value in checks.values()):
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "version": __version__, "checks": checks},
        )
    return ReadinessOut(status="ok", version=__version__, checks=checks)


@router.get("/metrics", include_in_schema=False)
def metrics(
    request: Request,
    authorization: str | None = Header(default=None),
    api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> Response:
    settings = get_settings()
    if not settings.metrics_enabled:
        raise HTTPException(status_code=404, detail="metrics are disabled")
    if settings.metrics_token:
        token = ""
        if authorization and authorization.lower().startswith("bearer "):
            token = authorization[7:].strip()
        if not hmac.compare_digest(token, settings.metrics_token):
            raise HTTPException(status_code=401, detail="metrics token required")
    elif settings.auth_mode.lower() != "disabled":
        principal = authenticate(request, authorization=authorization, api_key=api_key)
        principal.require("admin")
    return Response(
        render_metrics(__version__),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@router.get("/version")
def version() -> dict[str, str]:
    return {"name": "ErasureProof", "version": __version__}


def _tenant_request_ids(database: Database, tenant_id: str | None) -> set[str] | None:
    if tenant_id is None:
        return None
    with database.session() as session:
        return set(
            session.scalars(select(RequestRow.id).where(RequestRow.tenant_id == tenant_id)).all()
        )


@router.get("/v1/policies")
def list_policies(principal: Principal = Depends(require_viewer)) -> dict:
    registry = get_policies()
    return {
        "jurisdictions": registry.jurisdictions(),
        "policies": {j: registry.get(j).to_dict() for j in registry.jurisdictions()},
    }


@router.get("/v1/ledger")
def read_ledger(
    limit: int = Query(default=100, ge=1, le=1000),
    database: Database = Depends(get_db),
    principal: Principal = Depends(require_viewer),
) -> dict:
    ledger = get_ledger()
    entries = ledger.read()
    allowed = _tenant_request_ids(
        database, None if principal.tenant_wildcard else principal.tenant_id
    )
    if allowed is not None:
        entries = [entry for entry in entries if entry.request_id and entry.request_id in allowed]
    return {
        "head": ledger.head(),
        "count": len(entries),
        "entries": [entry.to_dict() for entry in entries[-limit:]],
    }


@router.post("/v1/ledger/verify", response_model=LedgerVerifyOut)
def verify_ledger(principal: Principal = Depends(require_viewer)) -> LedgerVerifyOut:
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
    database: Database = Depends(get_db),
    principal: Principal = Depends(require_viewer),
) -> dict:
    store = get_store()
    allowed = _tenant_request_ids(
        database, None if principal.tenant_wildcard else principal.tenant_id
    )
    items = []
    for path in store.meta.glob("*.json"):
        try:
            metadata = store.metadata(path.stem)
        except (FileNotFoundError, ValueError):
            continue
        item_request_id = metadata.get("request_id")
        if request_id and item_request_id != request_id:
            continue
        if allowed is not None and item_request_id not in allowed:
            continue
        if source and source.lower() not in str(metadata.get("source", "")).lower():
            continue
        metadata.pop("path", None)
        items.append(metadata)
    items.sort(key=lambda item: item.get("captured_at", ""), reverse=True)
    return {"count": len(items), "items": items[:limit]}


def _authorized_evidence(
    evidence_id: str,
    database: Database,
    principal: Principal,
) -> dict:
    store = get_store()
    try:
        metadata = store.metadata(evidence_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="evidence not found") from exc
    allowed = _tenant_request_ids(
        database, None if principal.tenant_wildcard else principal.tenant_id
    )
    if allowed is not None and metadata.get("request_id") not in allowed:
        raise HTTPException(status_code=404, detail="evidence not found")
    return metadata


@router.get("/v1/evidence/{evidence_id}")
def get_evidence(
    evidence_id: str,
    database: Database = Depends(get_db),
    principal: Principal = Depends(require_viewer),
) -> dict:
    evidence_id = _safe_evidence_id(evidence_id)
    metadata = _authorized_evidence(evidence_id, database, principal)
    metadata.pop("path", None)
    return metadata


@router.get("/v1/evidence/{evidence_id}/content")
def get_evidence_content(
    evidence_id: str,
    database: Database = Depends(get_db),
    principal: Principal = Depends(require_viewer),
):
    evidence_id = _safe_evidence_id(evidence_id)
    metadata = _authorized_evidence(evidence_id, database, principal)
    store = get_store()
    path = store.object_path(metadata)
    if not path.exists():
        raise HTTPException(status_code=404, detail="evidence object missing")
    return FileResponse(
        path,
        media_type=metadata.get("content_type", "application/octet-stream"),
        filename=evidence_id,
        content_disposition_type="inline",
    )


@router.post("/v1/evidence/{evidence_id}/verify")
def verify_evidence(
    evidence_id: str,
    database: Database = Depends(get_db),
    principal: Principal = Depends(require_viewer),
) -> dict:
    evidence_id = _safe_evidence_id(evidence_id)
    _authorized_evidence(evidence_id, database, principal)
    store = get_store()
    try:
        valid = store.verify(evidence_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="evidence not found") from exc
    return {"evidence_id": evidence_id, "valid": valid}
