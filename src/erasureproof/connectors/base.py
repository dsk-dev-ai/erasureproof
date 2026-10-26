"""Connector SDK.

A connector is the only component that touches a customer system. It exposes
discovery, remediation and flow/restore control through a small, uniform
interface. Write connectors for the systems that matter most; the engine handles
identity, policy, ordering, evidence and attestation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from ..models.domain import (
    Action,
    ActionResult,
    BackupRef,
    FlowRef,
    ResourceRef,
    State,
    SubjectGraph,
    VerificationOperation,
    VerificationResult,
)


class BaseConnector(ABC):
    type = "base"
    supports_discovery = True
    supports_remediation = True
    supports_verification = False
    supports_flow_control = False
    supports_restore_control = False

    def __init__(
        self,
        connector_id: str,
        system_id: str,
        config: dict[str, Any] | None = None,
        evidence_store: Any | None = None,
    ) -> None:
        self.connector_id = connector_id
        self.system_id = system_id
        self.config = config or {}
        self.evidence_store = evidence_store

    def capabilities(self) -> set[str]:
        capabilities = {"discover"}
        if self.supports_remediation:
            capabilities.add("remediate")
        if self.supports_flow_control:
            capabilities.add("disable_flow")
        if self.supports_restore_control:
            capabilities.add("block_restore")
        return capabilities

    @abstractmethod
    def discover(self, subject: SubjectGraph, as_of: datetime) -> list[ResourceRef]:
        """Return every record matching any identifier in the subject graph."""

    def discover_flows(self, subject: SubjectGraph, as_of: datetime) -> list[FlowRef]:
        return []

    def discover_backups(self, subject: SubjectGraph, as_of: datetime) -> list[BackupRef]:
        return []

    def snapshot(self, ref: ResourceRef, as_of: datetime | None = None) -> bytes | dict:
        raise NotImplementedError(f"{self.type} connector does not implement snapshots")

    def remediate(
        self, ref: ResourceRef, action: Action, fields: tuple[str, ...] = ()
    ) -> ActionResult:
        return ActionResult(
            self.system_id,
            ref.resource_id,
            action.value,
            success=False,
            supported=False,
            detail="remediation not supported by this connector",
        )

    def verify(self, ref: ResourceRef, expected: State) -> VerificationResult:
        return VerificationResult(
            operation=VerificationOperation.VERIFY_RECORD_PRESENT,
            system_id=self.system_id,
            resource_id=ref.resource_id,
            expected=expected,
            actual=State.PRESENT,
            passed=False,
            detail="verification not supported by this connector",
        )

    def disable_flow(self, flow: FlowRef) -> ActionResult:
        return ActionResult(
            self.system_id,
            flow.flow_id,
            "DISABLE_DATA_FLOW",
            success=False,
            supported=False,
            detail="flow control not supported by this connector",
        )

    def block_restore(self, backup: BackupRef) -> ActionResult:
        return ActionResult(
            self.system_id,
            backup.backup_id,
            "BLOCK_RESTORE",
            success=False,
            supported=False,
            detail="restore control not supported by this connector",
        )

    def close(self) -> None:
        return None

    def _record_evidence(
        self,
        content: bytes | str | dict | list,
        source: str,
        captured_at: datetime,
    ) -> str:
        if self.evidence_store is None:
            return ""
        return self.evidence_store.put(content, source=source, captured_at=captured_at).evidence_id
