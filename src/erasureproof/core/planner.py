"""Remediation planning.

Turns a policy decision plus a live inventory into an ordered plan:

1. FINDING  — what remains and which flows/backups could recreate it.
2. REMEDIATION — stop flows, block restores, then delete/redact downstream
   copies before their sources.
3. VERIFICATION — checks that must pass afterwards.
"""

from __future__ import annotations

from ..models.domain import (
    Action,
    BackupRef,
    Category,
    FindingOperation,
    FlowRef,
    Phase,
    Plan,
    RemediationOperation,
    ResourceRef,
    State,
    Step,
    VerificationOperation,
)
from .policy import Decision, Policy, is_compliant

CATEGORY_ORDER: dict[Category, int] = {
    Category.EXPORT: 0,
    Category.SEARCH_INDEX: 1,
    Category.ANALYTICS: 2,
    Category.LOG: 3,
    Category.SUPPORT: 4,
    Category.REPLICA: 5,
    Category.ARCHIVE: 6,
    Category.PRIMARY_ACCOUNT: 7,
    Category.TOMBSTONE: 8,
    Category.BACKUP: 9,
    Category.AUDIT_TRAIL: 10,
    Category.LEGAL_HOLD: 11,
}


def _resource_sort_key(resource: ResourceRef) -> tuple[int, str, str]:
    return (CATEGORY_ORDER.get(resource.category, 99), resource.system_id, resource.resource_id)


def _dedupe(items, key):
    seen = set()
    result = []
    for item in items:
        value = key(item)
        if value in seen:
            continue
        seen.add(value)
        result.append(item)
    return result


class PlanBuilder:
    def __init__(self, request_id: str, policy: Policy) -> None:
        self.request_id = request_id
        self.policy = policy

    def build(
        self,
        resources: list[ResourceRef],
        flows: list[FlowRef] | None = None,
        backups: list[BackupRef] | None = None,
    ) -> Plan:
        resources = sorted(_dedupe(resources, lambda r: r.key), key=_resource_sort_key)
        flows = sorted(_dedupe(flows or [], lambda f: f.key), key=lambda f: f.key)
        backups = sorted(_dedupe(backups or [], lambda b: b.key), key=lambda b: b.key)

        findings: list[Step] = []
        remediation: list[Step] = []
        verification: list[tuple[Step, str]] = []

        for flow in flows:
            if flow.is_active():
                findings.append(
                    Step(
                        0,
                        Phase.FINDING,
                        flow.system_id,
                        flow.flow_id,
                        FindingOperation.REPORT_ACTIVE_DATA_FLOW.value,
                        State.ACTIVE,
                        flow.evidence_id,
                    )
                )
                remediation.append(
                    Step(
                        0,
                        Phase.REMEDIATION,
                        flow.system_id,
                        flow.flow_id,
                        RemediationOperation.DISABLE_DATA_FLOW.value,
                        State.DISABLED,
                        "",
                    )
                )
                verification.append(
                    (
                        Step(
                            0,
                            Phase.VERIFICATION,
                            flow.system_id,
                            flow.flow_id,
                            VerificationOperation.VERIFY_DATA_FLOW_DISABLED.value,
                            State.DISABLED,
                            "",
                        ),
                        flow.evidence_id,
                    )
                )
            else:
                verification.append(
                    (
                        Step(
                            0,
                            Phase.VERIFICATION,
                            flow.system_id,
                            flow.flow_id,
                            VerificationOperation.VERIFY_DATA_FLOW_DISABLED.value,
                            State.DISABLED,
                            "",
                        ),
                        flow.evidence_id,
                    )
                )

        for backup in backups:
            if backup.restore_risk:
                findings.append(
                    Step(
                        0,
                        Phase.FINDING,
                        backup.system_id,
                        backup.backup_id,
                        FindingOperation.REPORT_RESTORE_RISK.value,
                        State.ACTIVE,
                        backup.evidence_id,
                    )
                )
                remediation.append(
                    Step(
                        0,
                        Phase.REMEDIATION,
                        backup.system_id,
                        backup.backup_id,
                        RemediationOperation.BLOCK_RESTORE.value,
                        State.BLOCKED,
                        "",
                    )
                )
            verification.append(
                (
                    Step(
                        0,
                        Phase.VERIFICATION,
                        backup.system_id,
                        backup.backup_id,
                        VerificationOperation.VERIFY_RESTORE_BLOCKED.value,
                        State.BLOCKED,
                        "",
                    ),
                    backup.evidence_id,
                )
            )

        for resource in resources:
            decision = self.policy.decide(resource)
            self._plan_resource(resource, decision, findings, remediation, verification)

        resource_categories = {r.key: r.category for r in resources}
        for step in findings + remediation + [item[0] for item in verification]:
            step.category = resource_categories.get(f"{step.system_id}:{step.resource_id}")

        incomplete = bool(findings)
        for index, (step, complete_evidence) in enumerate(verification, start=0):
            step.evidence_id = "" if incomplete else complete_evidence
            verification[index] = (step, step.evidence_id)

        plan = Plan(request_id=self.request_id, status="INCOMPLETE" if incomplete else "COMPLETE")
        plan.steps = findings + remediation + [step for step, _ in verification]
        return plan.renumber()

    def _plan_resource(
        self,
        resource: ResourceRef,
        decision: Decision,
        findings: list[Step],
        remediation: list[Step],
        verification: list[tuple[Step, str]],
    ) -> None:
        if decision.action is Action.DELETE:
            findings.append(
                Step(
                    0,
                    Phase.FINDING,
                    resource.system_id,
                    resource.resource_id,
                    FindingOperation.REPORT_REMAINING_RECORD.value,
                    State.PRESENT,
                    resource.evidence_id,
                )
            )
            remediation.append(
                Step(
                    0,
                    Phase.REMEDIATION,
                    resource.system_id,
                    resource.resource_id,
                    RemediationOperation.DELETE_RECORD.value,
                    State.ABSENT,
                    "",
                )
            )
            verification.append(
                (
                    Step(
                        0,
                        Phase.VERIFICATION,
                        resource.system_id,
                        resource.resource_id,
                        VerificationOperation.VERIFY_RECORD_ABSENT.value,
                        State.ABSENT,
                        "",
                    ),
                    resource.evidence_id,
                )
            )
            return

        if decision.action is Action.RETAIN:
            verification.append(
                (
                    Step(
                        0,
                        Phase.VERIFICATION,
                        resource.system_id,
                        resource.resource_id,
                        VerificationOperation.VERIFY_RECORD_PRESENT.value,
                        State.PRESENT,
                        "",
                    ),
                    resource.evidence_id,
                )
            )
            return

        if decision.action is Action.ANONYMIZE:
            if is_compliant(resource, decision):
                verification.append(
                    (
                        Step(
                            0,
                            Phase.VERIFICATION,
                            resource.system_id,
                            resource.resource_id,
                            VerificationOperation.VERIFY_RECORD_ANONYMIZED.value,
                            State.ANONYMIZED,
                            "",
                        ),
                        resource.evidence_id,
                    )
                )
            else:
                findings.append(
                    Step(
                        0,
                        Phase.FINDING,
                        resource.system_id,
                        resource.resource_id,
                        FindingOperation.REPORT_EXPOSED_PII.value,
                        State.PRESENT,
                        resource.evidence_id,
                    )
                )
                remediation.append(
                    Step(
                        0,
                        Phase.REMEDIATION,
                        resource.system_id,
                        resource.resource_id,
                        RemediationOperation.ANONYMIZE_RECORD.value,
                        State.ANONYMIZED,
                        "",
                    )
                )
                verification.append(
                    (
                        Step(
                            0,
                            Phase.VERIFICATION,
                            resource.system_id,
                            resource.resource_id,
                            VerificationOperation.VERIFY_RECORD_ANONYMIZED.value,
                            State.ANONYMIZED,
                            "",
                        ),
                        resource.evidence_id,
                    )
                )
            return

        if decision.action in (Action.REDACT, Action.TOMBSTONE):
            if not is_compliant(resource, decision):
                findings.append(
                    Step(
                        0,
                        Phase.FINDING,
                        resource.system_id,
                        resource.resource_id,
                        FindingOperation.REPORT_EXPOSED_PII.value,
                        State.PRESENT,
                        resource.evidence_id,
                    )
                )
                remediation.append(
                    Step(
                        0,
                        Phase.REMEDIATION,
                        resource.system_id,
                        resource.resource_id,
                        RemediationOperation.REDACT_RECORD.value,
                        State.REDACTED,
                        "",
                    )
                )
            verification.append(
                (
                    Step(
                        0,
                        Phase.VERIFICATION,
                        resource.system_id,
                        resource.resource_id,
                        VerificationOperation.VERIFY_RECORD_REDACTED.value,
                        State.REDACTED,
                        "",
                    ),
                    resource.evidence_id,
                )
            )
            if decision.action is Action.TOMBSTONE:
                verification.append(
                    (
                        Step(
                            0,
                            Phase.VERIFICATION,
                            resource.system_id,
                            resource.resource_id,
                            VerificationOperation.VERIFY_RECORD_PRESENT.value,
                            State.PRESENT,
                            "",
                        ),
                        resource.evidence_id,
                    )
                )


def build_plan(
    request_id: str,
    policy: Policy,
    resources: list[ResourceRef],
    flows: list[FlowRef] | None = None,
    backups: list[BackupRef] | None = None,
) -> Plan:
    return PlanBuilder(request_id, policy).build(resources, flows, backups)
