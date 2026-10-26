"""In-process orchestration.

The runner is deliberately small: discover, plan, remediate (optionally),
re-discover, verify, attest. Temporal wraps this same unit of work when a
deployment needs durable retries and long-running human approvals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ..connectors.base import BaseConnector
from ..core.attestation import AttestationService
from ..core.graph import StepGraph, build_step_graph, optimise_plan
from ..core.planner import build_plan
from ..core.policy import Policy, PolicyRegistry
from ..core.verifier import verification_passed, verify_plan
from ..evidence.ledger import EvidenceLedger
from ..evidence.store import EvidenceStore
from ..models.domain import (
    Action,
    ActionResult,
    Attestation,
    BackupRef,
    FlowRef,
    Phase,
    Plan,
    ResourceRef,
    SubjectGraph,
    VerificationResult,
)


@dataclass
class Discovery:
    resources: list[ResourceRef] = field(default_factory=list)
    flows: list[FlowRef] = field(default_factory=list)
    backups: list[BackupRef] = field(default_factory=list)
    owners: dict[tuple[str, str], BaseConnector] = field(default_factory=dict)
    refs: dict[str, ResourceRef] = field(default_factory=dict)
    flow_owners: dict[tuple[str, str], BaseConnector] = field(default_factory=dict)
    backup_owners: dict[tuple[str, str], BaseConnector] = field(default_factory=dict)
    flow_refs: dict[str, FlowRef] = field(default_factory=dict)
    backup_refs: dict[str, BackupRef] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


@dataclass
class RunResult:
    request_id: str
    status: str
    plan: Plan
    resources: list[ResourceRef]
    flows: list[FlowRef]
    backups: list[BackupRef]
    verifications: list[VerificationResult]
    actions: list[ActionResult]
    attestation: Attestation | None
    ledger_head: str
    remediation_applied: bool
    graph: StepGraph | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return verification_passed(self.verifications)

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "status": self.status,
            "plan": self.plan.to_dict(),
            "graph": self.graph.to_dict() if self.graph else None,
            "verification": [v.to_dict() for v in self.verifications],
            "actions": [action.to_dict() for action in self.actions],
            "attestation": self.attestation.to_dict() if self.attestation else None,
            "ledger_head": self.ledger_head,
            "remediation_applied": self.remediation_applied,
            "errors": self.errors,
        }


class ErasureOrchestrator:
    def __init__(
        self,
        connectors: list[BaseConnector],
        policy: Policy | PolicyRegistry,
        evidence_store: EvidenceStore,
        ledger: EvidenceLedger,
        attestations: AttestationService,
    ) -> None:
        self.connectors = connectors
        self.policy_source = policy
        self.evidence_store = evidence_store
        self.ledger = ledger
        self.attestations = attestations

    def close(self) -> None:
        for connector in self.connectors:
            connector.close()

    def _policy_for(self, jurisdiction: str | None) -> Policy:
        if isinstance(self.policy_source, PolicyRegistry):
            return self.policy_source.get(jurisdiction)
        return self.policy_source

    def discover(self, subject: SubjectGraph, as_of: datetime) -> Discovery:
        discovery = Discovery()
        for connector in self.connectors:
            try:
                resources = connector.discover(subject, as_of)
            except Exception as exc:  # pragma: no cover - connector defensive
                discovery.errors.append(f"{connector.system_id}: discover failed: {exc}")
                resources = []

            for resource in resources:
                key = resource.key
                if key in discovery.refs:
                    continue
                discovery.resources.append(resource)
                discovery.refs[key] = resource
                discovery.owners[(resource.system_id, resource.resource_id)] = connector

            try:
                flows = connector.discover_flows(subject, as_of)
            except Exception as exc:  # pragma: no cover
                discovery.errors.append(f"{connector.system_id}: flow discovery failed: {exc}")
                flows = []

            for flow in flows:
                if flow.key in discovery.flow_refs:
                    continue
                discovery.flows.append(flow)
                discovery.flow_refs[flow.key] = flow
                discovery.flow_owners[(flow.system_id, flow.flow_id)] = connector

            try:
                backups = connector.discover_backups(subject, as_of)
            except Exception as exc:  # pragma: no cover
                discovery.errors.append(f"{connector.system_id}: backup discovery failed: {exc}")
                backups = []

            for backup in backups:
                if backup.key in discovery.backup_refs:
                    continue
                discovery.backups.append(backup)
                discovery.backup_refs[backup.key] = backup
                discovery.backup_owners[(backup.system_id, backup.backup_id)] = connector

        return discovery

    def run(
        self,
        request_id: str,
        subject: SubjectGraph,
        audit_at: datetime,
        jurisdiction: str | None = None,
        remediate: bool = True,
        attest: bool = True,
        extra: dict[str, Any] | None = None,
    ) -> RunResult:
        if audit_at.tzinfo is None:
            audit_at = audit_at.replace(tzinfo=timezone.utc)

        policy = self._policy_for(jurisdiction)
        self.ledger.append(
            "discovery.started",
            request_id,
            {"subject_user_id": subject.user_id, "audit_at": audit_at.isoformat()},
        )

        initial = self.discover(subject, audit_at)
        plan = build_plan(
            request_id,
            policy,
            initial.resources,
            initial.flows,
            initial.backups,
        )
        plan = optimise_plan(plan)
        graph = build_step_graph(plan)
        self.ledger.append(
            "plan.created",
            request_id,
            {
                "status": plan.status,
                "steps": len(plan.steps),
                "findings": len(plan.findings()),
                "jurisdiction": policy.jurisdiction,
            },
        )

        actions: list[ActionResult] = []
        remediation_applied = False
        current = initial

        if remediate and plan.status == "INCOMPLETE":
            actions = self._remediate(plan, policy, initial, request_id)
            remediation_applied = True
            current = self.discover(subject, audit_at)
            self.ledger.append(
                "remediation.completed",
                request_id,
                {
                    "actions": len(actions),
                    "successful": sum(1 for action in actions if action.success),
                    "errors": len(current.errors),
                },
            )

        owners = {**initial.owners, **current.owners}
        refs = {**initial.refs, **current.refs}
        verifications = verify_plan(
            plan,
            current.resources,
            current.flows,
            current.backups,
            owners=owners,
            refs=refs,
        )

        passed = verification_passed(verifications)
        if remediation_applied:
            status = "COMPLETE" if passed else "INCOMPLETE"
        else:
            status = plan.status

        self.ledger.append(
            "verification.completed",
            request_id,
            {
                "status": status,
                "passed": passed,
                "checks": len(verifications),
                "failed": sum(1 for result in verifications if not result.passed),
            },
        )

        graph = build_step_graph(plan)
        attestation: Attestation | None = None
        if attest:
            head = self.ledger.head()
            attestation = self.attestations.issue(
                request_id=request_id,
                status=status,
                plan=plan,
                verifications=verifications,
                ledger_head=head,
                extra={
                    "subject_user_id": subject.user_id,
                    "audit_at": audit_at.isoformat(),
                    "remediation_applied": remediation_applied,
                    "step_graph": graph.to_dict(),
                    **(extra or {}),
                },
            )
            self.ledger.append(
                "attestation.issued",
                request_id,
                {"status": status, "path": attestation.path},
            )

        return RunResult(
            request_id=request_id,
            status=status,
            plan=plan,
            resources=current.resources,
            flows=current.flows,
            backups=current.backups,
            verifications=verifications,
            actions=actions,
            attestation=attestation,
            ledger_head=self.ledger.head(),
            remediation_applied=remediation_applied,
            graph=graph,
            errors=initial.errors + current.errors,
        )

    def _remediate(
        self,
        plan: Plan,
        policy: Policy,
        discovery: Discovery,
        request_id: str,
    ) -> list[ActionResult]:
        actions: list[ActionResult] = []
        for step in plan.steps:
            if step.phase is not Phase.REMEDIATION:
                continue
            key = f"{step.system_id}:{step.resource_id}"

            if step.operation == "DISABLE_DATA_FLOW":
                connector = discovery.flow_owners.get((step.system_id, step.resource_id))
                flow = discovery.flow_refs.get(key)
                if connector is None or flow is None:
                    result = ActionResult(
                        step.system_id,
                        step.resource_id,
                        step.operation,
                        False,
                        detail="flow not found",
                    )
                else:
                    result = connector.disable_flow(flow)
            elif step.operation == "BLOCK_RESTORE":
                connector = discovery.backup_owners.get((step.system_id, step.resource_id))
                backup = discovery.backup_refs.get(key)
                if connector is None or backup is None:
                    result = ActionResult(
                        step.system_id,
                        step.resource_id,
                        step.operation,
                        False,
                        detail="backup not found",
                    )
                else:
                    result = connector.block_restore(backup)
            else:
                connector = discovery.owners.get((step.system_id, step.resource_id))
                ref = discovery.refs.get(key)
                if connector is None or ref is None:
                    result = ActionResult(
                        step.system_id,
                        step.resource_id,
                        step.operation,
                        False,
                        detail="record not found",
                    )
                else:
                    decision = policy.decide(ref)
                    if step.operation == "DELETE_RECORD":
                        action = Action.DELETE
                    elif step.operation == "ANONYMIZE_RECORD":
                        action = Action.ANONYMIZE
                    elif decision.action is Action.TOMBSTONE:
                        action = Action.TOMBSTONE
                    else:
                        action = Action.REDACT
                    result = connector.remediate(ref, action, decision.redact_fields)

            actions.append(result)
            self.ledger.append(
                "remediation.action",
                request_id,
                {
                    "operation": step.operation,
                    "system_id": step.system_id,
                    "resource_id": step.resource_id,
                    "success": result.success,
                    "detail": result.detail,
                },
            )
        return actions
