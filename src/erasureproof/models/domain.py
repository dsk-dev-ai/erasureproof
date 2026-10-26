"""Core domain types.

These types are intentionally framework-free so the identity, policy, planning
and evidence logic can be tested in isolation and reused from the API worker,
the CLI and the orchestrator.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class IdentifierType(str, Enum):
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    EMAIL_HASH = "EMAIL_HASH"
    EXTERNAL_ID = "EXTERNAL_ID"


class Category(str, Enum):
    PRIMARY_ACCOUNT = "PRIMARY_ACCOUNT"
    REPLICA = "REPLICA"
    SEARCH_INDEX = "SEARCH_INDEX"
    ANALYTICS = "ANALYTICS"
    SUPPORT = "SUPPORT"
    EXPORT = "EXPORT"
    LOG = "LOG"
    ARCHIVE = "ARCHIVE"
    BACKUP = "BACKUP"
    TOMBSTONE = "TOMBSTONE"
    AUDIT_TRAIL = "AUDIT_TRAIL"
    LEGAL_HOLD = "LEGAL_HOLD"


class Action(str, Enum):
    DELETE = "DELETE"
    REDACT = "REDACT"
    ANONYMIZE = "ANONYMIZE"
    RETAIN = "RETAIN"
    TOMBSTONE = "TOMBSTONE"


class Phase(str, Enum):
    FINDING = "FINDING"
    REMEDIATION = "REMEDIATION"
    VERIFICATION = "VERIFICATION"


class FindingOperation(str, Enum):
    REPORT_REMAINING_RECORD = "REPORT_REMAINING_RECORD"
    REPORT_EXPOSED_PII = "REPORT_EXPOSED_PII"
    REPORT_ACTIVE_DATA_FLOW = "REPORT_ACTIVE_DATA_FLOW"
    REPORT_RESTORE_RISK = "REPORT_RESTORE_RISK"


class RemediationOperation(str, Enum):
    DISABLE_DATA_FLOW = "DISABLE_DATA_FLOW"
    BLOCK_RESTORE = "BLOCK_RESTORE"
    DELETE_RECORD = "DELETE_RECORD"
    REDACT_RECORD = "REDACT_RECORD"
    ANONYMIZE_RECORD = "ANONYMIZE_RECORD"


class VerificationOperation(str, Enum):
    VERIFY_RECORD_ABSENT = "VERIFY_RECORD_ABSENT"
    VERIFY_RECORD_PRESENT = "VERIFY_RECORD_PRESENT"
    VERIFY_RECORD_REDACTED = "VERIFY_RECORD_REDACTED"
    VERIFY_RECORD_ANONYMIZED = "VERIFY_RECORD_ANONYMIZED"
    VERIFY_DATA_FLOW_DISABLED = "VERIFY_DATA_FLOW_DISABLED"
    VERIFY_RESTORE_BLOCKED = "VERIFY_RESTORE_BLOCKED"


class State(str, Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    REDACTED = "REDACTED"
    ANONYMIZED = "ANONYMIZED"
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    BLOCKED = "BLOCKED"


class RequestStatus(str, Enum):
    NOT_APPLICABLE = "NOT_APPLICABLE"
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

_PHONE_RE = re.compile(r"[^0-9+]")


def normalize_value(value: str, identifier_type: IdentifierType) -> str:
    """Return a stable, comparable representation of an identifier."""

    value = (value or "").strip()
    if identifier_type in (IdentifierType.EMAIL, IdentifierType.EMAIL_HASH):
        return value.lower()
    if identifier_type is IdentifierType.PHONE:
        digits = _PHONE_RE.sub("", value)
        if digits.startswith("00"):
            digits = "+" + digits[2:]
        return digits
    return value.lower()


def hash_email(email: str) -> str:
    return hashlib.sha256(normalize_value(email, IdentifierType.EMAIL).encode()).hexdigest()


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Identifier:
    type: IdentifierType
    value: str
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    source: str = "unknown"

    def normalized(self) -> str:
        return normalize_value(self.value, self.type)

    def is_valid_at(self, when: datetime | None) -> bool:
        if when is None:
            return True
        if self.valid_from and self.valid_from > when:
            return False
        if self.valid_to and self.valid_to < when:
            return False
        return True


@dataclass(slots=True)
class KnownSubject:
    user_id: str
    identifiers: list[Identifier] = field(default_factory=list)


@dataclass(slots=True)
class SubjectGraph:
    user_id: str
    identifiers: list[Identifier]
    matched_by: str = "unknown"
    confidence: float = 1.0

    def values(self) -> set[str]:
        return {i.normalized() for i in self.identifiers if i.normalized()}

    def email_values(self) -> set[str]:
        return {
            i.normalized()
            for i in self.identifiers
            if i.type is IdentifierType.EMAIL
        }


@dataclass(slots=True)
class ResourceRef:
    system_id: str
    resource_id: str
    category: Category
    connector_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    exposed_fields: list[str] = field(default_factory=list)
    evidence_id: str = ""

    @property
    def key(self) -> str:
        return f"{self.system_id}:{self.resource_id}"


@dataclass(slots=True)
class FlowRef:
    system_id: str
    flow_id: str
    source: str = ""
    dest: str = ""
    status: str = "ACTIVE"
    evidence_id: str = ""

    @property
    def key(self) -> str:
        return f"{self.system_id}:{self.flow_id}"

    def is_active(self) -> bool:
        return self.status.upper() not in {"DISABLED", "INACTIVE", "STOPPED", "BLOCKED"}


@dataclass(slots=True)
class BackupRef:
    system_id: str
    backup_id: str
    restore_risk: bool = True
    evidence_id: str = ""

    @property
    def key(self) -> str:
        return f"{self.system_id}:{self.backup_id}"


@dataclass(slots=True)
class Snapshot:
    resource: ResourceRef
    captured_at: datetime
    content_hash: str
    content: dict[str, Any]


@dataclass(slots=True)
class Finding:
    operation: FindingOperation
    system_id: str
    resource_id: str
    state: State
    evidence_id: str = ""
    category: Category | None = None
    detail: str = ""
    resource: ResourceRef | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation": self.operation.value,
            "system_id": self.system_id,
            "resource_id": self.resource_id,
            "state": self.state.value,
            "evidence_id": self.evidence_id,
            "category": self.category.value if self.category else None,
            "detail": self.detail,
        }


@dataclass(slots=True)
class Step:
    step_no: int
    phase: Phase
    system_id: str
    resource_id: str
    operation: str
    state: State
    evidence_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_no": self.step_no,
            "phase": self.phase.value,
            "system_id": self.system_id,
            "resource_id": self.resource_id,
            "operation": self.operation,
            "state": self.state.value,
            "evidence_id": self.evidence_id,
        }


@dataclass(slots=True)
class Plan:
    request_id: str
    steps: list[Step] = field(default_factory=list)
    status: str = "PLANNED"

    def renumber(self) -> Plan:
        for index, step in enumerate(self.steps, start=1):
            step.step_no = index
        return self

    def findings(self) -> list[Step]:
        return [s for s in self.steps if s.phase is Phase.FINDING]

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "status": self.status,
            "steps": [s.to_dict() for s in self.steps],
        }


@dataclass(slots=True)
class VerificationResult:
    operation: VerificationOperation
    system_id: str
    resource_id: str
    expected: State
    actual: State
    passed: bool
    detail: str = ""
    evidence_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation": self.operation.value,
            "system_id": self.system_id,
            "resource_id": self.resource_id,
            "expected": self.expected.value,
            "actual": self.actual.value,
            "passed": self.passed,
            "detail": self.detail,
            "evidence_id": self.evidence_id,
        }


@dataclass(slots=True)
class ActionResult:
    system_id: str
    resource_id: str
    operation: str
    success: bool
    supported: bool = True
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "system_id": self.system_id,
            "resource_id": self.resource_id,
            "operation": self.operation,
            "success": self.success,
            "supported": self.supported,
            "detail": self.detail,
        }


@dataclass(slots=True)
class Attestation:
    request_id: str
    status: str
    issued_at: datetime
    payload: dict[str, Any]
    signature: str
    path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "status": self.status,
            "issued_at": self.issued_at.isoformat(),
            "signature": self.signature,
            "path": self.path,
            "payload": self.payload,
        }
