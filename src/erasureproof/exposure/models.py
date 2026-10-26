"""Exposure report types and risk scoring."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ..intelligence.identifiers import mask_identifier
from ..models.domain import IdentifierType, normalize_value

KIND_WEIGHTS = {
    "breach": 45,
    "paste": 38,
    "code": 32,
    "public_document": 28,
    "social": 22,
    "profile": 18,
    "archive": 16,
    "direct": 24,
    "search": 12,
    "domain": 10,
}

KIND_SEVERITY = {
    "breach": "CRITICAL",
    "paste": "HIGH",
    "code": "HIGH",
    "public_document": "HIGH",
    "social": "MEDIUM",
    "profile": "MEDIUM",
    "archive": "MEDIUM",
    "direct": "MEDIUM",
    "search": "LOW",
    "domain": "LOW",
}

_SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "NONE": 4}


def _mask(value: str) -> str:
    return mask_identifier(value)


def _mask_text(text: str, values: list[str]) -> str:
    for value in sorted((item for item in values if len(item) >= 3), key=len, reverse=True):
        text = re.sub(re.escape(value), _mask(value), text, flags=re.IGNORECASE)
    return text


@dataclass(slots=True)
class ExposureTarget:
    email: str | None = None
    phone: str | None = None
    name: str | None = None
    usernames: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)

    def emails(self) -> list[str]:
        return [normalize_value(self.email, IdentifierType.EMAIL)] if self.email else []

    def phones(self) -> list[str]:
        return [normalize_value(self.phone, IdentifierType.PHONE)] if self.phone else []

    def names(self) -> list[str]:
        return [self.name.strip()] if self.name and len(self.name.strip()) >= 3 else []

    def all_values(self) -> list[str]:
        values = [*self.emails(), *self.phones(), *self.names(), *self.usernames]
        return [value for value in values if value]

    def query_terms(self) -> list[str]:
        terms: list[str] = []
        for value in self.emails() + self.phones():
            terms.append(value)
        if self.name:
            terms.append(self.name.strip())
        terms.extend(self.usernames)
        return list(dict.fromkeys(term for term in terms if len(term) >= 3))

    def masked(self) -> dict[str, Any]:
        return {
            "email": _mask(self.email) if self.email else None,
            "phone": _mask(self.phone) if self.phone else None,
            "name": _mask(self.name) if self.name else None,
            "usernames": [_mask(value) for value in self.usernames],
            "urls": list(self.urls),
        }


@dataclass(slots=True)
class ExposureHit:
    collector: str
    kind: str
    url: str
    title: str = ""
    snippet: str = ""
    identifiers: list[str] = field(default_factory=list)
    status: str = "OPEN"
    confidence: float = 0.7
    first_seen: str | None = None
    last_seen: str | None = None
    evidence_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def severity(self) -> str:
        return KIND_SEVERITY.get(self.kind, "MEDIUM")

    @property
    def weight(self) -> int:
        base = KIND_WEIGHTS.get(self.kind, 12)
        return min(100, base + min(15, 3 * len(self.identifiers)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "collector": self.collector,
            "kind": self.kind,
            "severity": self.severity,
            "url": self.url,
            "title": _mask_text(self.title, self.identifiers),
            "snippet": _mask_text(self.snippet, self.identifiers),
            "identifiers": [_mask(value) for value in self.identifiers],
            "status": self.status,
            "confidence": round(self.confidence, 2),
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "evidence_id": self.evidence_id,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class ExposureReport:
    target: ExposureTarget
    generated_at: datetime
    hits: list[ExposureHit] = field(default_factory=list)
    collectors: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    risk_score: int = 0
    severity: str = "NONE"
    recommendations: list[str] = field(default_factory=list)
    report_evidence_id: str = ""
    authorized: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "target": self.target.masked(),
            "authorized": self.authorized,
            "collectors": list(self.collectors),
            "hits": [hit.to_dict() for hit in self.hits],
            "hit_count": len(self.hits),
            "errors": list(self.errors),
            "risk_score": self.risk_score,
            "severity": self.severity,
            "recommendations": list(self.recommendations),
            "report_evidence_id": self.report_evidence_id,
        }

    def sorted_hits(self) -> list[ExposureHit]:
        return sorted(
            self.hits,
            key=lambda hit: (
                _SEVERITY_ORDER.get(hit.severity, 9),
                -hit.confidence,
                hit.url,
            ),
        )


def score_report(hits: list[ExposureHit]) -> tuple[int, str, list[str]]:
    if not hits:
        return (
            0,
            "NONE",
            [
                "No public exposure was confirmed by the selected collectors.",
                "Re-run periodically and after deleting first-party records.",
            ],
        )
    weights = sorted((hit.weight for hit in hits), reverse=True)
    score = min(100, weights[0] + 4 * (len(weights) - 1))
    if any(hit.kind == "breach" for hit in hits):
        score = max(score, 60)
    if score >= 80:
        severity = "CRITICAL"
    elif score >= 55:
        severity = "HIGH"
    elif score >= 30:
        severity = "MEDIUM"
    else:
        severity = "LOW"

    recommendations: list[str] = []
    kinds = {hit.kind for hit in hits}
    if "breach" in kinds:
        recommendations.append(
            "Treat credentials as compromised: rotate passwords, revoke sessions and enable MFA."
        )
    if "code" in kinds:
        recommendations.append(
            "Remove secrets or identifiers from source control and rewrite history where required."
        )
    if "public_document" in kinds or "direct" in kinds:
        recommendations.append(
            "Request removal at the source, then re-scan the URL and common archives."
        )
    if "archive" in kinds or "search" in kinds:
        recommendations.append(
            "After removing the source, request cache/archive removal and re-indexing."
        )
    if "profile" in kinds or "social" in kinds:
        recommendations.append(
            "Close or sanitise the public profile and review linked accounts."
        )
    recommendations.extend(
        [
            "Record evidence before remediation; the evidence IDs in this report are immutable.",
            "Re-run at 7, 30 and 90 days and keep the signed results with the erasure file.",
        ]
    )
    return score, severity, recommendations


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
