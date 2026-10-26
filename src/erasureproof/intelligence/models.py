"""Data types shared by the evidence-intelligence pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _mask(value: str) -> str:
    value = str(value)
    if "@" in value and "." in value.rsplit("@", 1)[-1]:
        local, _, domain = value.partition("@")
        return f"{local[:1]}***@{domain}"
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) >= 7:
        return f"{digits[:3]}***{digits[-2:]}"
    if len(value) <= 4:
        return "***"
    return f"{value[:2]}***{value[-2:]}"


def _mask_mapping(values: dict[str, list[str]]) -> dict[str, list[str]]:
    return {
        kind: sorted({_mask(value) for value in items})
        for kind, items in sorted(values.items())
    }


@dataclass(slots=True)
class ExtractedDocument:
    text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    pages: int = 0
    ocr_used: bool = False
    warnings: list[str] = field(default_factory=list)
    children: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pages": self.pages,
            "ocr_used": self.ocr_used,
            "warnings": list(self.warnings),
            "metadata": self.metadata,
            "children": list(self.children),
            "text_chars": len(self.text),
        }


@dataclass(slots=True)
class ScannedFile:
    path: str
    name: str
    sha256: str
    size: int
    mime: str
    modified_at: datetime
    identifiers: dict[str, list[str]] = field(default_factory=dict)
    matched: dict[str, list[str]] = field(default_factory=dict)
    snippets: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    evidence_id: str = ""
    ocr_used: bool = False
    warnings: list[str] = field(default_factory=list)

    @property
    def matched_count(self) -> int:
        return sum(len(values) for values in self.matched.values())

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "name": self.name,
            "sha256": self.sha256,
            "size": self.size,
            "mime": self.mime,
            "modified_at": self.modified_at.isoformat(),
            "identifiers": _mask_mapping(self.identifiers),
            "matched": _mask_mapping(self.matched),
            "matched_count": self.matched_count,
            "snippets": list(self.snippets),
            "metadata": self.metadata,
            "evidence_id": self.evidence_id,
            "ocr_used": self.ocr_used,
            "warnings": list(self.warnings),
        }


@dataclass(slots=True)
class ScanReport:
    root: str
    started_at: datetime
    completed_at: datetime
    scanned: int = 0
    matched_files: list[ScannedFile] = field(default_factory=list)
    identifiers: dict[str, list[str]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    tools: dict[str, str] = field(default_factory=dict)
    risk_score: int = 0
    severity: str = "NONE"
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "scanned": self.scanned,
            "matched": len(self.matched_files),
            "identifiers": _mask_mapping(self.identifiers),
            "files": [item.to_dict() for item in self.matched_files],
            "errors": list(self.errors),
            "tools": dict(self.tools),
            "risk_score": self.risk_score,
            "severity": self.severity,
            "recommendations": list(self.recommendations),
        }


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
