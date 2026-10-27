from __future__ import annotations

import base64
import json
import time

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi.testclient import TestClient

from erasureproof.api import auth
from erasureproof.config import get_settings, validate_runtime_settings
from erasureproof.main import app

client = TestClient(app)

ADMIN = {
    "key": "admin-key",
    "role": "admin",
    "tenant": "*",
    "subject": "admin-one@example.com",
}
ADMIN_TWO = {
    "key": "admin-two-key",
    "role": "admin",
    "tenant": "*",
    "subject": "admin-two@example.com",
}
VIEWER_A = {
    "key": "viewer-a-key",
    "role": "viewer",
    "tenant": "ten_auth_a",
    "subject": "viewer-a@example.com",
}
OPERATOR_A = {
    "key": "operator-a-key",
    "role": "operator",
    "tenant": "ten_auth_a",
    "subject": "operator-a@example.com",
}
OPERATOR_B = {
    "key": "operator-b-key",
    "role": "operator",
    "tenant": "ten_auth_b",
    "subject": "operator-b@example.com",
}


def _headers(entry: dict) -> dict[str, str]:
    return {"X-API-Key": entry["key"]}


def _configure(monkeypatch, *, approval: bool = False) -> None:
    monkeypatch.setenv("ERASUREPROOF_AUTH_MODE", "api_key")
    monkeypatch.setenv(
        "ERASUREPROOF_API_KEYS",
        json.dumps([ADMIN, ADMIN_TWO, VIEWER_A, OPERATOR_A, OPERATOR_B]),
    )
    monkeypatch.setenv("ERASUREPROOF_REQUIRE_REMEDIATION_APPROVAL", str(approval).lower())
    get_settings.cache_clear()


@pytest.fixture
def auth_enabled(monkeypatch):
    _configure(monkeypatch)
    yield
    get_settings.cache_clear()


@pytest.fixture
def approvals_enabled(monkeypatch):
    _configure(monkeypatch, approval=True)
    yield
    get_settings.cache_clear()


def _create_tenant(name: str) -> str:
    response = client.post(
        "/v1/tenants",
        json={"name": name, "jurisdiction": "gdpr"},
        headers=_headers(ADMIN),
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_request(tenant_id: str, operator: dict = OPERATOR_A) -> dict:
    response = client.post(
        "/v1/requests",
        json={
            "tenant_id": tenant_id,
            "email": "subject@example.com",
            "request_text": "Please delete my account and all my data.",
            "audit_at": "2026-10-26T00:00:00Z",
        },
        headers=_headers(operator),
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_api_key_auth_roles_and_tenant_isolation(auth_enabled, monkeypatch) -> None:
    tenant_a = _create_tenant("Auth A")
    tenant_b = _create_tenant("Auth B")

    viewer_a = {**VIEWER_A, "tenant": tenant_a}
    operator_a = {**OPERATOR_A, "tenant": tenant_a}
    operator_b = {**OPERATOR_B, "tenant": tenant_b}
    monkeypatch.setenv(
        "ERASUREPROOF_API_KEYS",
        json.dumps([ADMIN, ADMIN_TWO, viewer_a, operator_a, operator_b]),
    )
    get_settings.cache_clear()

    request_a = _create_request(tenant_a, operator_a)
    request_b = _create_request(tenant_b, operator_b)

    assert client.get("/v1/tenants").status_code == 401
    listed = client.get("/v1/tenants", headers=_headers(viewer_a))
    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()] == [tenant_a]

    assert (
        client.post(
            "/v1/tenants",
            json={"name": "Denied"},
            headers=_headers(viewer_a),
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/v1/tenants",
            json={"name": "Denied"},
            headers=_headers(operator_a),
        ).status_code
        == 403
    )

    assert (
        client.get(f"/v1/requests/{request_a['id']}", headers=_headers(viewer_a)).status_code == 200
    )
    assert (
        client.get(f"/v1/requests/{request_b['id']}", headers=_headers(viewer_a)).status_code == 404
    )
    assert client.get(f"/v1/requests/{request_a['id']}", headers=_headers(ADMIN)).status_code == 200

    overview = client.get("/v1/overview", headers=_headers(viewer_a))
    assert overview.status_code == 200
    assert overview.json()["totals"]["requests"] == 1
    assert overview.json()["tenant_id"] == tenant_a


def test_approval_gate_separate_user_and_audit_export(approvals_enabled) -> None:
    tenant = _create_tenant("Approval Co")
    request = _create_request(tenant, ADMIN)

    # Remediation is blocked until an approval exists.
    blocked = client.post(f"/v1/requests/{request['id']}/run?force=true", headers=_headers(ADMIN))
    assert blocked.status_code == 428

    # The request creator cannot approve their own destructive action.
    same = client.post(
        f"/v1/requests/{request['id']}/approval",
        json={"decision": "APPROVED", "reason": "self approval"},
        headers=_headers(ADMIN),
    )
    assert same.status_code == 409

    approved = client.post(
        f"/v1/requests/{request['id']}/approval",
        json={"decision": "APPROVED", "reason": "reviewed by second administrator"},
        headers=_headers(ADMIN_TWO),
    )
    assert approved.status_code == 201
    assert approved.json()["status"] == "APPROVED"

    listed = client.get(f"/v1/requests/{request['id']}/approvals", headers=_headers(VIEWER_A))
    # VIEWER_A is scoped to another tenant and must not see this approval.
    assert listed.status_code == 404

    run = client.post(f"/v1/requests/{request['id']}/run?force=true", headers=_headers(ADMIN))
    assert run.status_code == 200
    assert run.json()["status"] == "COMPLETE"

    current = client.get(f"/v1/requests/{request['id']}", headers=_headers(ADMIN)).json()
    assert current["approval_consumed_at"] is not None
    assert current["approved_by"] == ADMIN_TWO["subject"]

    replay = client.post(f"/v1/requests/{request['id']}/run?force=true", headers=_headers(ADMIN))
    assert replay.status_code == 428

    events = client.get("/v1/audit-events", headers=_headers(ADMIN))
    assert events.status_code == 200
    actions = {event["action"] for event in events.json()}
    assert {"request.created", "approval.approved", "approval.consumed"} <= actions

    assert client.get("/v1/audit-events", headers=_headers(VIEWER_A)).status_code == 403

    exported = client.get("/v1/audit-events/export", headers=_headers(ADMIN))
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("text/csv")
    assert "request.created" in exported.text


def test_metrics_require_admin_when_api_key_auth_is_enabled(auth_enabled) -> None:
    assert client.get("/metrics").status_code == 401
    assert client.get("/metrics", headers=_headers(VIEWER_A)).status_code == 403
    response = client.get("/metrics", headers=_headers(ADMIN))
    assert response.status_code == 200
    assert "erasureproof_build_info" in response.text


def test_security_headers_and_cors(auth_enabled) -> None:
    response = client.get("/healthz", headers={"Origin": "http://localhost:5173"})
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-request-id"]
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_rate_limit(monkeypatch) -> None:
    monkeypatch.setenv("ERASUREPROOF_AUTH_MODE", "api_key")
    monkeypatch.setenv("ERASUREPROOF_API_KEYS", json.dumps([ADMIN]))
    monkeypatch.setenv("ERASUREPROOF_RATE_LIMIT_PER_MINUTE", "1")
    get_settings.cache_clear()
    try:
        from erasureproof.middleware import _RATE_EVENTS

        _RATE_EVENTS.clear()
        first = client.get("/v1/tenants", headers=_headers(ADMIN))
        second = client.get("/v1/tenants", headers=_headers(ADMIN))
        assert first.status_code == 200
        assert second.status_code == 429
        assert second.headers["retry-after"]
    finally:
        get_settings.cache_clear()


def test_runtime_configuration_rejects_insecure_production() -> None:
    settings = get_settings().model_copy(
        update={"environment": "production", "auth_mode": "disabled"}
    )
    with pytest.raises(ValueError, match="authentication cannot be disabled"):
        validate_runtime_settings(settings)

    settings = get_settings().model_copy(
        update={
            "environment": "production",
            "auth_mode": "api_key",
            "api_keys": "",
            "attestation_key": "not-default",
        }
    )
    with pytest.raises(ValueError, match="API_KEYS"):
        validate_runtime_settings(settings)


def test_api_key_config_requires_scoped_tenant(monkeypatch) -> None:
    from erasureproof.config import Settings

    monkeypatch.setenv("ERASUREPROOF_AUTH_MODE", "api_key")
    monkeypatch.setenv(
        "ERASUREPROOF_API_KEYS",
        json.dumps(
            [
                {"key": "no-tenant", "role": "operator"},
                {"key": "wide-viewer", "role": "viewer", "tenant_id": "*"},
            ]
        ),
    )
    settings = Settings()
    with pytest.raises(ValueError, match="missing tenant"):
        validate_runtime_settings(settings)


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _jwt(key: rsa.RSAPrivateKey, kid: str, payload: dict) -> str:
    header = {"alg": "RS256", "kid": kid, "typ": "JWT"}
    header_b64 = _b64(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _b64(json.dumps(payload, separators=(",", ":")).encode())
    signature = key.sign(
        f"{header_b64}.{payload_b64}".encode(),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return f"{header_b64}.{payload_b64}.{_b64(signature)}"


def test_oidc_signature_claims_and_roles(monkeypatch) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    numbers = private_key.public_key().public_numbers()
    jwks = {
        "keys": [
            {
                "kty": "RSA",
                "kid": "test-key",
                "n": _b64(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")),
                "e": _b64(numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big")),
            }
        ]
    }
    monkeypatch.setattr(auth, "_fetch_jwks", lambda *_: jwks)
    monkeypatch.setenv("ERASUREPROOF_AUTH_MODE", "oidc")
    monkeypatch.setenv("ERASUREPROOF_OIDC_ISSUER", "https://issuer.example")
    monkeypatch.setenv("ERASUREPROOF_OIDC_AUDIENCE", "erasureproof")
    monkeypatch.setenv("ERASUREPROOF_OIDC_JWKS_URL", "https://issuer.example/jwks")
    monkeypatch.setenv("ERASUREPROOF_OIDC_DEFAULT_ROLE", "viewer")
    get_settings.cache_clear()
    try:
        now = int(time.time())
        unscoped = _jwt(
            private_key,
            "test-key",
            {
                "sub": "oidc-user",
                "iss": "https://issuer.example",
                "aud": "erasureproof",
                "exp": now + 300,
                "roles": ["viewer"],
            },
        )
        response = client.get("/v1/tenants", headers={"Authorization": f"Bearer {unscoped}"})
        assert response.status_code == 401

        admin_token = _jwt(
            private_key,
            "test-key",
            {
                "sub": "oidc-admin",
                "iss": "https://issuer.example",
                "aud": "erasureproof",
                "exp": now + 300,
                "roles": ["admin"],
                "tenant_id": "*",
            },
        )
        created = client.post(
            "/v1/tenants",
            json={"name": "OIDC Co", "jurisdiction": "gdpr"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert created.status_code == 201
        tenant_id = created.json()["id"]

        token = _jwt(
            private_key,
            "test-key",
            {
                "sub": "oidc-user",
                "iss": "https://issuer.example",
                "aud": "erasureproof",
                "exp": now + 300,
                "roles": ["viewer"],
                "tenant_id": tenant_id,
            },
        )
        response = client.get("/v1/tenants", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert [row["id"] for row in response.json()] == [tenant_id]

        wildcard_viewer = _jwt(
            private_key,
            "test-key",
            {
                "sub": "oidc-viewer",
                "iss": "https://issuer.example",
                "aud": "erasureproof",
                "exp": now + 300,
                "roles": ["viewer"],
                "tenant_id": "*",
            },
        )
        assert (
            client.get(
                "/v1/tenants", headers={"Authorization": f"Bearer {wildcard_viewer}"}
            ).status_code
            == 401
        )

        expired = _jwt(
            private_key,
            "test-key",
            {
                "sub": "oidc-user",
                "iss": "https://issuer.example",
                "aud": "erasureproof",
                "exp": now - 300,
                "roles": ["admin"],
                "tenant_id": "*",
            },
        )
        assert (
            client.get("/v1/tenants", headers={"Authorization": f"Bearer {expired}"}).status_code
            == 401
        )

        wrong_audience = _jwt(
            private_key,
            "test-key",
            {
                "sub": "oidc-user",
                "iss": "https://issuer.example",
                "aud": "another-service",
                "exp": now + 300,
                "roles": ["admin"],
                "tenant_id": "*",
            },
        )
        assert (
            client.get(
                "/v1/tenants", headers={"Authorization": f"Bearer {wrong_audience}"}
            ).status_code
            == 401
        )
    finally:
        get_settings.cache_clear()
