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


def test_overview_lists_requests_and_demo_workspace() -> None:
    tenant = _tenant()
    request = _request(tenant, "Please delete my account.")
    client.post(f"/v1/requests/{request['id']}/run")

    overview = client.get(f"/v1/overview?tenant_id={tenant}").json()
    assert overview["totals"]["requests"] == 1
    assert overview["totals"]["attestations"] == 1
    assert overview["attestation_coverage"] == 100.0
    assert overview["statuses"]["COMPLETE"] == 1
    assert overview["recent_requests"][0]["id"] == request["id"]
    assert overview["ledger"]["head"]
    assert overview["policies"]

    requests = client.get(f"/v1/requests?tenant_id={tenant}").json()
    assert [row["id"] for row in requests] == [request["id"]]

    demo = client.post("/v1/demo/seed").json()
    assert demo["created"] is True
    assert demo["audit_status"] == "INCOMPLETE"
    assert demo["complete_status"] == "COMPLETE"


def test_evidence_endpoints() -> None:
    from erasureproof.api.deps import get_store

    record = get_store().put(
        '{"email": "alice@example.com"}',
        source="test:evidence",
        content_type="application/json",
    )
    listing = client.get("/v1/evidence?source=test:evidence&limit=10").json()
    assert any(item["evidence_id"] == record.evidence_id for item in listing["items"])

    metadata = client.get(f"/v1/evidence/{record.evidence_id}").json()
    assert metadata["source"] == "test:evidence"
    assert "path" not in metadata

    content = client.get(f"/v1/evidence/{record.evidence_id}/content")
    assert content.status_code == 200
    assert b"alice@example.com" in content.content
    assert content.headers["content-disposition"].startswith("inline")

    verified = client.post(f"/v1/evidence/{record.evidence_id}/verify").json()
    assert verified["valid"] is True


def test_console_serves_spa_and_client_routes() -> None:
    from pathlib import Path

    import pytest

    if not (Path("web") / "dist" / "index.html").is_file():
        pytest.skip("web console has not been built")
    response = client.get("/console")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "ErasureProof" in response.text

    nested = client.get("/console/app/requests/demo")
    assert nested.status_code == 200
    assert "text/html" in nested.headers["content-type"]

    head = client.head("/console")
    assert head.status_code == 200
    assert "text/html" in head.headers["content-type"]
