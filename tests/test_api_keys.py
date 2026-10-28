from __future__ import annotations

import json
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from erasureproof.api.routes import onboarding
from erasureproof.config import get_settings
from erasureproof.main import app
from erasureproof.models.db import ApiKeyRow, get_database
from erasureproof.models.domain import utcnow

client = TestClient(app)
BOOTSTRAP = {
    "key": "bootstrap-key",
    "role": "admin",
    "tenant": "*",
    "subject": "bootstrap@example.com",
}
BOOT = {"X-API-Key": BOOTSTRAP["key"]}


@pytest.fixture
def product_auth(monkeypatch):
    monkeypatch.setenv("ERASUREPROOF_AUTH_MODE", "api_key")
    monkeypatch.setenv("ERASUREPROOF_API_KEYS", json.dumps([BOOTSTRAP]))
    monkeypatch.setenv("ERASUREPROOF_SELF_SERVE_ENABLED", "true")
    monkeypatch.setenv("ERASUREPROOF_SANDBOX_PER_IP_DAILY_LIMIT", "10")
    get_settings.cache_clear()
    onboarding._SANDBOX_GLOBAL.clear()
    onboarding._SANDBOX_BY_IP.clear()
    yield
    get_settings.cache_clear()


def _tenant(name: str) -> str:
    response = client.post(
        "/v1/tenants", json={"name": name, "jurisdiction": "gdpr"}, headers=BOOT
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_sandbox_is_isolated_and_usable_end_to_end(product_auth) -> None:
    response = client.post(
        "/v1/onboarding/sandbox",
        json={"workspace_name": "Developer Trial", "jurisdiction": "gdpr"},
    )
    assert response.status_code == 201, response.text
    sandbox = response.json()
    assert sandbox["api_key"].startswith("ep_live_")
    assert sandbox["sample_request_id"].startswith("req_")
    headers = {"X-API-Key": sandbox["api_key"]}

    tenants = client.get("/v1/tenants", headers=headers)
    assert tenants.status_code == 200
    assert [row["id"] for row in tenants.json()] == [sandbox["tenant_id"]]

    request = client.get(f"/v1/requests/{sandbox['sample_request_id']}", headers=headers)
    assert request.status_code == 200
    assert request.json()["email"] == sandbox["sample_email"]

    run = client.post(
        f"/v1/requests/{sandbox['sample_request_id']}/run?remediate=false",
        headers=headers,
    )
    assert run.status_code == 200, run.text
    assert run.json()["status"] in {"INCOMPLETE", "COMPLETE", "NOT_APPLICABLE"}
    assert run.json()["attestation"]["signature"]

    attestation = client.get(
        f"/v1/requests/{sandbox['sample_request_id']}/attestation", headers=headers
    )
    assert attestation.status_code == 200

    keys = client.get("/v1/api-keys", headers=headers)
    assert keys.status_code == 200
    assert len(keys.json()) == 1
    assert "api_key" not in keys.json()[0]
    assert "key_hash" not in keys.json()[0]


def test_api_key_rotation_revocation_and_roles(product_auth) -> None:
    tenant = _tenant("Key Lifecycle Co")
    created = client.post(
        "/v1/api-keys",
        json={"tenant_id": tenant, "name": "CI operator", "role": "operator"},
        headers=BOOT,
    )
    assert created.status_code == 201
    first = created.json()
    operator_headers = {"X-API-Key": first["api_key"]}

    assert client.get("/v1/tenants", headers=operator_headers).status_code == 200
    denied = client.post(
        "/v1/api-keys",
        json={"tenant_id": tenant, "name": "Nope", "role": "viewer"},
        headers=operator_headers,
    )
    assert denied.status_code == 403

    rotated = client.post(f"/v1/api-keys/{first['id']}/rotate", headers=BOOT)
    assert rotated.status_code == 201
    second = rotated.json()
    assert second["api_key"] != first["api_key"]
    assert client.get("/v1/tenants", headers=operator_headers).status_code == 401
    replacement_headers = {"X-API-Key": second["api_key"]}
    assert client.get("/v1/tenants", headers=replacement_headers).status_code == 200

    revoked = client.delete(f"/v1/api-keys/{second['id']}", headers=BOOT)
    assert revoked.status_code == 204
    assert client.get("/v1/tenants", headers=replacement_headers).status_code == 401

    database = get_database()
    with database.session() as session:
        rows = session.scalars(select(ApiKeyRow).where(ApiKeyRow.tenant_id == tenant)).all()
        assert len(rows) == 2
        assert all(len(row.key_hash) == 64 for row in rows)
        assert all(row.key_hash != first["api_key"] for row in rows)
        assert all(row.key_hash != second["api_key"] for row in rows)


def test_expired_key_is_rejected(product_auth) -> None:
    tenant = _tenant("Expiry Co")
    created = client.post(
        "/v1/api-keys",
        json={"tenant_id": tenant, "name": "Temporary", "role": "viewer"},
        headers=BOOT,
    ).json()
    database = get_database()
    with database.session() as session:
        row = session.get(ApiKeyRow, created["id"])
        assert row is not None
        row.expires_at = utcnow() - timedelta(minutes=1)
    response = client.get("/v1/tenants", headers={"X-API-Key": created["api_key"]})
    assert response.status_code == 401
    assert "expired" in response.json()["detail"]


def test_self_serve_can_be_disabled(monkeypatch) -> None:
    monkeypatch.setenv("ERASUREPROOF_AUTH_MODE", "api_key")
    monkeypatch.setenv("ERASUREPROOF_API_KEYS", json.dumps([BOOTSTRAP]))
    monkeypatch.setenv("ERASUREPROOF_SELF_SERVE_ENABLED", "false")
    get_settings.cache_clear()
    response = client.post("/v1/onboarding/sandbox", json={})
    assert response.status_code == 404
    get_settings.cache_clear()
