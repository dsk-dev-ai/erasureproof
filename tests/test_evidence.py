from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from erasureproof.core.attestation import AttestationService
from erasureproof.evidence.ledger import EvidenceLedger
from erasureproof.evidence.store import EvidenceStore
from erasureproof.models.domain import (
    Phase,
    Plan,
    State,
    Step,
)


def test_content_addressed_store(tmp_path) -> None:
    store = EvidenceStore(tmp_path / "evidence")
    captured = datetime.now(timezone.utc)

    first = store.put({"email": "alice@example.com"}, source="db", captured_at=captured)
    second = store.put({"email": "alice@example.com"}, source="db", captured_at=captured)

    assert first.evidence_id == second.evidence_id
    assert first.sha256 == second.sha256
    assert store.exists(first.evidence_id)
    assert store.verify(first.evidence_id)
    assert json.loads(store.get(first.evidence_id)) == {"email": "alice@example.com"}
    assert store.metadata(first.evidence_id)["source"] == "db"


def test_ledger_hash_chain_detects_tampering(tmp_path) -> None:
    ledger = EvidenceLedger(tmp_path / "ledger.jsonl")
    ledger.append("request.created", "req_1", {"email_hash": "abc"})
    ledger.append("discovery.started", "req_1", {"records": 3})

    valid, _ = ledger.verify()
    assert valid

    lines = ledger.path.read_text(encoding="utf-8").splitlines()
    entry = json.loads(lines[0])
    entry["payload"]["email_hash"] = "tampered"
    lines[0] = json.dumps(entry)
    ledger.path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    valid, detail = ledger.verify()
    assert not valid
    assert "hash mismatch" in detail


def test_attestation_signature_and_tamper_detection(tmp_path) -> None:
    service = AttestationService("secret-key", tmp_path / "attestations")
    plan = Plan(
        request_id="req_1",
        steps=[
            Step(
                1,
                Phase.VERIFICATION,
                "db",
                "record:1",
                "VERIFY_RECORD_ABSENT",
                State.ABSENT,
                "ev_1",
            )
        ],
        status="COMPLETE",
    )

    attestation = service.issue("req_1", "COMPLETE", plan=plan, ledger_head="abc")

    valid, payload = service.verify_file(attestation.path)
    assert valid
    assert payload["request_id"] == "req_1"
    assert payload["summary"]["step_count"] == 1

    document = json.loads(Path(attestation.path).read_text(encoding="utf-8"))
    document["payload"]["status"] = "INCOMPLETE"
    with open(attestation.path, "w", encoding="utf-8") as handle:
        json.dump(document, handle)

    valid, _ = service.verify_file(attestation.path)
    assert not valid


def test_attestation_rejects_wrong_key(tmp_path) -> None:
    service = AttestationService("secret-key", tmp_path / "attestations")
    attestation = service.issue("req_2", "NOT_APPLICABLE", plan=Plan("req_2", [], "NOT_APPLICABLE"))

    other = AttestationService("different-key", tmp_path / "other")
    valid, _ = other.verify_file(attestation.path)
    assert not valid
