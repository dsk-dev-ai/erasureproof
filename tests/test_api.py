from __future__ import annotations

from fastapi.testclient import TestClient

from erasureproof.config import get_settings
from erasureproof.core.attestation import AttestationService
from erasureproof.main import app

client = TestClient(app)


def _tenant() -> str:
    response = client.post(
        "/v1/tenants", json={"name": "Test Co", "jurisdiction": "gdpr"}
    )
    assert response.status_code == 201
    return response.json()["id"]


def _request(tenant_id: str, text: str) -> dict:
    response = client.post(
        "/v1/requests",
        json={
            "tenant_id": tenant_id,
            "email": "alice@example.com",
            "request_text": text,
            "audit_at": "2026-10-26T00:00:00Z",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_health_and_connector_types() -> None:
    assert client.get("/healthz").json()["status"] == "ok"
    types = client.get("/v1/connector-types").json()["types"]
    assert {"sql", "postgres", "local", "s3", "control", "filesystem"} <= set(types)


def test_non_deletion_request_is_not_applicable() -> None:
    tenant = _tenant()
    request = _request(tenant, "Please send me a copy of all my personal data.")
    assert request["status"] == "NOT_APPLICABLE"

    run = client.post(f"/v1/requests/{request['id']}/run").json()
    assert run["status"] == "NOT_APPLICABLE"
    assert run["plan"]["steps"] == []
    assert run["verification"] == []
    assert run["attestation"]["signature"]

    attestation = client.get(f"/v1/requests/{request['id']}/attestation").json()
    assert attestation["status"] == "NOT_APPLICABLE"


def test_deletion_request_with_no_connectors_completes() -> None:
    tenant = _tenant()
    request = _request(tenant, "Please delete my account.")
    assert request["status"] == "PENDING"

    run = client.post(f"/v1/requests/{request['id']}/run").json()
    assert run["status"] == "COMPLETE"
    assert run["plan"]["status"] == "COMPLETE"
    assert run["remediation_applied"] is False
    assert run["attestation"]["status"] == "COMPLETE"

    settings = get_settings()
    valid, payload = AttestationService(
        settings.attestation_key, settings.attestation_dir
    ).verify_file(run["attestation"]["path"])
    assert valid
    assert payload["request_id"] == request["id"]


def test_exposure_endpoint_is_disabled_by_default() -> None:
    response = client.post(
        "/v1/exposure/scan",
        json={
            "email": "alice@example.com",
            "collectors": ["direct"],
            "authorized": True,
        },
    )
    assert response.status_code == 403
    assert "disabled" in response.json()["detail"]


def test_request_graph_endpoint_renders_json_mermaid_and_dot() -> None:
    tenant = _tenant()
    request = _request(tenant, "Please delete my account.")
    client.post(f"/v1/requests/{request['id']}/run")

    graph = client.get(f"/v1/requests/{request['id']}/graph")
    assert graph.status_code == 200
    payload = graph.json()
    assert payload["request_id"] == request["id"]
    assert "nodes" in payload and "order" in payload

    mermaid = client.get(f"/v1/requests/{request['id']}/graph?format=mermaid")
    assert mermaid.status_code == 200
    assert mermaid.text.startswith("flowchart TD")
    dot = client.get(f"/v1/requests/{request['id']}/graph?format=dot")
    assert dot.status_code == 200
    assert dot.text.startswith("digraph erasureproof")


def test_ledger_endpoint_verifies() -> None:
    tenant = _tenant()
    request = _request(tenant, "Please delete my account.")
    client.post(f"/v1/requests/{request['id']}/run")

    verification = client.post("/v1/ledger/verify").json()
    assert verification["valid"] is True
    ledger = client.get("/v1/ledger?limit=5").json()
    assert ledger["count"] >= 1
    assert len(ledger["entries"]) <= 5
