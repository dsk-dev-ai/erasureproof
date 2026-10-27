"""HTTP API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..models.domain import IdentifierType


class TenantCreate(BaseModel):
    name: str
    jurisdiction: str = "gdpr"


class TenantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    jurisdiction: str
    created_at: datetime


class IdentifierIn(BaseModel):
    type: IdentifierType
    value: str
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    source: str = "api"


class SubjectCreate(BaseModel):
    tenant_id: str
    user_id: str
    identifiers: list[IdentifierIn] = Field(default_factory=list)


class SubjectOut(BaseModel):
    id: str
    tenant_id: str
    user_id: str
    identifiers: list[IdentifierIn] = Field(default_factory=list)
    created_at: datetime


class ConnectorCreate(BaseModel):
    tenant_id: str
    type: str
    name: str
    config: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class ConnectorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    type: str
    name: str
    config: dict[str, Any]
    enabled: bool
    created_at: datetime


class RequestCreate(BaseModel):
    tenant_id: str
    email: str
    request_text: str
    requested_at: datetime | None = None
    audit_at: datetime
    jurisdiction: str | None = None
    remediate: bool = True


class RequestOut(BaseModel):
    id: str
    tenant_id: str
    email: str
    status: str
    request_text: str
    requested_at: datetime
    audit_at: datetime
    jurisdiction: str
    result: dict[str, Any] | None = None
    plan: dict[str, Any] | None = None
    approval_status: str | None = None
    approval_expires_at: datetime | None = None
    approval_consumed_at: datetime | None = None
    approved_by: str | None = None


class ApprovalDecision(BaseModel):
    decision: Literal["APPROVED", "REJECTED"]
    reason: str = Field(default="", max_length=2000)


class ApprovalOut(BaseModel):
    id: str
    request_id: str
    tenant_id: str
    status: str
    requested_by: str
    decided_by: str | None
    reason: str
    created_at: datetime
    decided_at: datetime | None
    expires_at: datetime | None
    consumed_at: datetime | None


class AuditEventOut(BaseModel):
    id: str
    tenant_id: str | None
    actor: str
    actor_role: str
    action: str
    resource_type: str
    resource_id: str
    request_id: str | None
    detail: dict[str, Any]
    created_at: datetime


class RunResponse(BaseModel):
    request_id: str
    status: str
    plan: dict[str, Any]
    graph: dict[str, Any] | None = None
    verification: list[dict[str, Any]]
    actions: list[dict[str, Any]]
    attestation: dict[str, Any] | None
    ledger_head: str
    remediation_applied: bool
    errors: list[str] = Field(default_factory=list)


class AttestationOut(BaseModel):
    request_id: str
    status: str
    signature: str
    path: str
    payload: dict[str, Any]


class LedgerVerifyOut(BaseModel):
    valid: bool
    detail: str
    head: str


class HealthOut(BaseModel):
    status: Literal["ok"] = "ok"
    version: str
    database: str


class ReadinessOut(BaseModel):
    status: Literal["ok"] = "ok"
    version: str
    checks: dict[str, str]


class ExposureScanRequest(BaseModel):
    tenant_id: str | None = None
    email: str | None = None
    phone: str | None = None
    name: str | None = None
    usernames: list[str] = Field(default_factory=list)
    urls: list[str] = Field(default_factory=list)
    collectors: list[str] | None = None
    authorized: bool = False
