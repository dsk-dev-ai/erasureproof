from __future__ import annotations

from pathlib import Path

from erasureproof.config import get_settings
from erasureproof.core.attestation import AttestationService
from erasureproof.demo import run_demo
from erasureproof.evidence.ledger import EvidenceLedger


def test_demo_end_to_end() -> None:
    result = run_demo()

    assert result.status == "COMPLETE"
    assert result.remediation_applied
    assert len(result.plan.findings()) >= 8
    assert result.verifications
    assert all(verification.passed for verification in result.verifications)
    assert result.errors == []

    assert any(
        action.operation == "DISABLE_DATA_FLOW" and action.success
        for action in result.actions
    )
    assert any(
        action.operation == "BLOCK_RESTORE" and action.success for action in result.actions
    )

    acted_on = {action.resource_id for action in result.actions}
    assert "exports/future_export.json" not in acted_on
    assert (get_settings().data_dir / "demo" / "bucket" / "exports" / "future_export.json").exists()

    assert result.attestation is not None
    valid, payload = AttestationService(
        get_settings().attestation_key,
        get_settings().attestation_dir,
    ).verify_file(result.attestation.path)
    assert valid
    assert payload["status"] == "COMPLETE"

    ledger = EvidenceLedger(get_settings().ledger_path)
    valid_chain, detail = ledger.verify()
    assert valid_chain, detail
    assert Path(result.attestation.path).exists()
