from __future__ import annotations

from erasureproof.core.planner import build_plan
from erasureproof.core.policy import default_policy
from erasureproof.models.domain import (
    BackupRef,
    Category,
    FlowRef,
    Phase,
    ResourceRef,
)


def test_incomplete_plan_orders_phases_and_dependencies() -> None:
    resources = [
        ResourceRef(
            "account_service",
            "account:501",
            Category.PRIMARY_ACCOUNT,
            payload={"name": "Alice", "email": "alice@example.com"},
            exposed_fields=["name", "email"],
            evidence_id="ev_account",
        ),
        ResourceRef(
            "search_service",
            "doc:9001",
            Category.SEARCH_INDEX,
            evidence_id="ev_search",
        ),
    ]
    flows = [FlowRef("sync_service", "flow_crm", evidence_id="ev_flow")]
    backups = [BackupRef("backup_service", "backup_weekly", evidence_id="ev_backup")]

    plan = build_plan("req_1", default_policy(), resources, flows, backups)

    assert plan.status == "INCOMPLETE"
    assert [step.step_no for step in plan.steps] == list(range(1, len(plan.steps) + 1))
    phases = [step.phase for step in plan.steps]
    assert phases == [Phase.FINDING] * 4 + [Phase.REMEDIATION] * 4 + [
        Phase.VERIFICATION
    ] * len([s for s in plan.steps if s.phase is Phase.VERIFICATION])

    findings = plan.findings()
    assert {finding.evidence_id for finding in findings} == {
        "ev_account",
        "ev_search",
        "ev_flow",
        "ev_backup",
    }

    remediation = [s for s in plan.steps if s.phase is Phase.REMEDIATION]
    assert remediation[0].operation == "DISABLE_DATA_FLOW"
    assert remediation[1].operation == "BLOCK_RESTORE"
    assert remediation[2].operation == "DELETE_RECORD"
    assert remediation[3].operation == "REDACT_RECORD"

    for step in plan.steps:
        if step.phase is Phase.REMEDIATION:
            assert step.evidence_id == ""
        if step.phase is Phase.VERIFICATION:
            assert step.evidence_id == ""


def test_complete_plan_has_evidence_backed_verification_only() -> None:
    resources = [
        ResourceRef(
            "db",
            "audit:1",
            Category.AUDIT_TRAIL,
            payload={"user_id": "u_1"},
            evidence_id="ev_audit",
        )
    ]
    plan = build_plan("req_2", default_policy(), resources)

    assert plan.status == "COMPLETE"
    assert len(plan.steps) == 1
    step = plan.steps[0]
    assert step.phase is Phase.VERIFICATION
    assert step.operation == "VERIFY_RECORD_PRESENT"
    assert step.state.value == "PRESENT"
    assert step.evidence_id == "ev_audit"


def test_compliant_tombstone_is_complete_and_verified() -> None:
    resources = [
        ResourceRef(
            "db",
            "tombstone:1",
            Category.TOMBSTONE,
            payload={"user_id": "u_1"},
            exposed_fields=[],
            evidence_id="ev_tombstone",
        )
    ]
    plan = build_plan("req_3", default_policy(), resources)

    assert plan.status == "COMPLETE"
    operations = [step.operation for step in plan.steps]
    assert operations == ["VERIFY_RECORD_REDACTED", "VERIFY_RECORD_PRESENT"]
    assert all(step.evidence_id == "ev_tombstone" for step in plan.steps)


def test_active_flow_and_restore_risk_are_findings() -> None:
    plan = build_plan(
        "req_4",
        default_policy(),
        [],
        [FlowRef("sync", "flow_1", evidence_id="ev_flow")],
        [BackupRef("backup", "b_1", evidence_id="ev_backup")],
    )
    assert plan.status == "INCOMPLETE"
    assert [step.operation for step in plan.findings()] == [
        "REPORT_ACTIVE_DATA_FLOW",
        "REPORT_RESTORE_RISK",
    ]
