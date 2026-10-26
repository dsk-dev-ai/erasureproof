"""Post-remediation verification.

Verification is evidence-driven: it re-reads the live inventory rather than
trusting an action's success flag.
"""

from __future__ import annotations

from ..models.domain import (
    BackupRef,
    FlowRef,
    Phase,
    Plan,
    ResourceRef,
    State,
    VerificationOperation,
    VerificationResult,
)


def _actual_record_state(
    operation: VerificationOperation,
    resources: dict[str, ResourceRef],
    key: str,
) -> State:
    resource = resources.get(key)

    if operation is VerificationOperation.VERIFY_RECORD_ABSENT:
        return State.ABSENT if resource is None else State.PRESENT
    if operation is VerificationOperation.VERIFY_RECORD_PRESENT:
        return State.PRESENT if resource is not None else State.ABSENT
    if operation is VerificationOperation.VERIFY_RECORD_REDACTED:
        if resource is None:
            return State.ABSENT
        if resource.payload.get("redacted") is True:
            return State.REDACTED
        return State.PRESENT if resource.exposed_fields else State.REDACTED
    if operation is VerificationOperation.VERIFY_RECORD_ANONYMIZED:
        if resource is None:
            return State.ABSENT
        if resource.payload.get("anonymized") is True or resource.payload.get("linked") is False:
            return State.ANONYMIZED
        return State.PRESENT
    return State.PRESENT


_RECORD_OPERATIONS = {
    VerificationOperation.VERIFY_RECORD_ABSENT.value,
    VerificationOperation.VERIFY_RECORD_PRESENT.value,
    VerificationOperation.VERIFY_RECORD_REDACTED.value,
    VerificationOperation.VERIFY_RECORD_ANONYMIZED.value,
}


def verify_plan(
    plan: Plan,
    resources: list[ResourceRef],
    flows: list[FlowRef] | None = None,
    backups: list[BackupRef] | None = None,
    owners: dict[tuple[str, str], object] | None = None,
    refs: dict[str, ResourceRef] | None = None,
) -> list[VerificationResult]:
    resource_map = {r.key: r for r in resources}
    flow_map = {f.key: f for f in (flows or [])}
    backup_map = {b.key: b for b in (backups or [])}
    owners = owners or {}
    refs = refs or {}

    results: list[VerificationResult] = []
    for step in plan.steps:
        if step.phase is not Phase.VERIFICATION:
            continue
        key = f"{step.system_id}:{step.resource_id}"
        evidence_id = ""
        operation = VerificationOperation(step.operation)

        owner = owners.get((step.system_id, step.resource_id))
        ref = refs.get(key)
        if (
            owner is not None
            and ref is not None
            and getattr(owner, "supports_verification", False)
            and step.operation in _RECORD_OPERATIONS
        ):
            result = owner.verify(ref, step.state)  # type: ignore[attr-defined]
            if not result.evidence_id:
                result.evidence_id = ref.evidence_id
            results.append(result)
            continue

        if operation is VerificationOperation.VERIFY_DATA_FLOW_DISABLED:
            flow = flow_map.get(key)
            actual = State.ACTIVE if flow is not None and flow.is_active() else State.DISABLED
            evidence_id = flow.evidence_id if flow else ""
        elif operation is VerificationOperation.VERIFY_RESTORE_BLOCKED:
            backup = backup_map.get(key)
            actual = State.ACTIVE if backup is not None and backup.restore_risk else State.BLOCKED
            evidence_id = backup.evidence_id if backup else ""
        else:
            actual = _actual_record_state(operation, resource_map, key)
            resource = resource_map.get(key)
            evidence_id = resource.evidence_id if resource else ""

        results.append(
            VerificationResult(
                operation=operation,
                system_id=step.system_id,
                resource_id=step.resource_id,
                expected=step.state,
                actual=actual,
                passed=actual is step.state,
                evidence_id=evidence_id,
            )
        )

    return results


def verification_passed(results: list[VerificationResult]) -> bool:
    return bool(results) and all(result.passed for result in results)
