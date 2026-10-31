from __future__ import annotations

from datetime import datetime, timedelta, timezone

from erasureproof.connectors.base import BaseConnector
from erasureproof.core.attestation import AttestationService
from erasureproof.core.policy import default_policy
from erasureproof.evidence.ledger import EvidenceLedger
from erasureproof.evidence.store import EvidenceStore
from erasureproof.models.domain import (
    ActionResult,
    Category,
    ResourceRef,
    State,
    SubjectGraph,
    VerificationOperation,
    VerificationResult,
)
from erasureproof.orchestrator.runner import ErasureOrchestrator

NOW = datetime.now(timezone.utc)


def _subject() -> SubjectGraph:
    return SubjectGraph(user_id="u_runner", identifiers=[])


def _orchestrator(tmp_path, connector: BaseConnector) -> ErasureOrchestrator:
    store = EvidenceStore(tmp_path / "evidence")
    return ErasureOrchestrator(
        connectors=[connector],
        policy=default_policy(),
        evidence_store=store,
        ledger=EvidenceLedger(tmp_path / "ledger.jsonl"),
        attestations=AttestationService("test-key", tmp_path / "attestations"),
    )


class BrokenConnector(BaseConnector):
    type = "broken"

    def discover(self, subject, as_of):
        raise RuntimeError("database unavailable")


class FailingVerifier(BaseConnector):
    type = "failing"
    supports_verification = True

    def discover(self, subject, as_of):
        return [
            ResourceRef(
                system_id="audit",
                resource_id="audit:1",
                category=Category.AUDIT_TRAIL,
                evidence_id="ev_audit",
            )
        ]

    def verify(self, ref, expected):
        return VerificationResult(
            operation=VerificationOperation.VERIFY_RECORD_PRESENT,
            system_id=ref.system_id,
            resource_id=ref.resource_id,
            expected=State.PRESENT,
            actual=State.ABSENT,
            passed=False,
            evidence_id=ref.evidence_id,
        )


class ReappearingConnector(BaseConnector):
    type = "reappearing"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.discoveries = 0

    def discover(self, subject, as_of):
        self.discoveries += 1
        if self.discoveries == 1:
            return [
                ResourceRef(
                    system_id="exports",
                    resource_id="export:old",
                    category=Category.SUPPORT,
                    evidence_id="ev_old",
                    exposed_fields=["email"],
                )
            ]
        return [
            ResourceRef(
                system_id="exports",
                resource_id="export:new",
                category=Category.SUPPORT,
                evidence_id="ev_new",
                exposed_fields=["email"],
            )
        ]

    def remediate(self, ref, action, fields=()):
        return ActionResult(ref.system_id, ref.resource_id, action.value, success=True)


def test_discovery_error_prevents_complete_status(tmp_path) -> None:
    orchestrator = _orchestrator(tmp_path, BrokenConnector("c1", "broken"))
    result = orchestrator.run(
        "req_broken",
        _subject(),
        NOW + timedelta(hours=1),
        remediate=False,
    )

    assert result.status == "INCOMPLETE"
    assert any("database unavailable" in error for error in result.errors)
    assert result.attestation is not None
    assert result.attestation.status == "INCOMPLETE"


def test_failed_verification_prevents_complete_status(tmp_path) -> None:
    orchestrator = _orchestrator(tmp_path, FailingVerifier("c2", "failing"))
    result = orchestrator.run(
        "req_failed_verification",
        _subject(),
        NOW + timedelta(hours=1),
        remediate=False,
    )

    assert result.plan.status == "COMPLETE"
    assert result.verifications
    assert not result.verifications[0].passed
    assert result.status == "INCOMPLETE"


def test_new_resource_after_remediation_prevents_complete_status(tmp_path) -> None:
    connector = ReappearingConnector("c3", "reappearing")
    orchestrator = _orchestrator(tmp_path, connector)
    result = orchestrator.run(
        "req_reappeared",
        _subject(),
        NOW + timedelta(hours=1),
        remediate=True,
    )

    assert result.remediation_applied
    assert result.status == "INCOMPLETE"
    assert any("not in the plan" in error for error in result.errors)
