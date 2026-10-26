"""Filesystem evidence connector.

This connector turns a directory of exports, attachments, logs, archives,
database snapshots and scans into discovery evidence. It uses the intelligence
pipeline (text, PDF, OCR, metadata, archive and SQLite extraction) so a match is
not limited to the file name or raw bytes.
"""

from __future__ import annotations

import fnmatch
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from ..canonical import sha256_hex
from ..intelligence.extract import ExtractionLimits, extract_file
from ..intelligence.identifiers import extract_identifiers, metadata_text
from ..models.domain import (
    Action,
    ActionResult,
    Category,
    ResourceRef,
    State,
    SubjectGraph,
    VerificationOperation,
    VerificationResult,
)
from .base import BaseConnector


class FilesystemConnector(BaseConnector):
    type = "filesystem"
    supports_remediation = True
    supports_verification = True

    def __init__(
        self,
        connector_id: str,
        system_id: str,
        config: dict[str, Any] | None = None,
        evidence_store: Any | None = None,
    ) -> None:
        super().__init__(connector_id, system_id, config, evidence_store)
        root = self.config.get("root")
        if not root:
            raise ValueError("Filesystem connector requires a 'root'")
        self.root = Path(str(root)).expanduser().resolve()
        self.categories = {
            str(pattern): Category(str(value).upper())
            for pattern, value in (self.config.get("categories") or {}).items()
        }
        self.default_category = Category(
            str(self.config.get("default_category", "EXPORT")).upper()
        )
        self.max_files = int(self.config.get("max_files", 5000))
        self.include_hidden = bool(self.config.get("include_hidden", False))
        self.names = [str(name) for name in self.config.get("names", [])]
        self.limits = ExtractionLimits(
            max_bytes=int(self.config.get("max_bytes", 8_000_000)),
            ocr=bool(self.config.get("ocr", True)),
            max_pages=int(self.config.get("max_pages", 20)),
            max_archive_entries=int(self.config.get("max_archive_entries", 200)),
        )

    def _safe_path(self, relative: str) -> Path | None:
        candidate = (self.root / relative).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError:
            return None
        return candidate

    def _category_for(self, relative: str) -> Category:
        matches = [
            (pattern, category)
            for pattern, category in self.categories.items()
            if fnmatch.fnmatch(relative, pattern) or relative.startswith(pattern.rstrip("*"))
        ]
        if not matches:
            return self.default_category
        return max(matches, key=lambda item: len(item[0]))[1]

    @staticmethod
    def _exposed_fields(matched: dict[str, list[str]]) -> list[str]:
        mapping = {
            "email": "email",
            "email_hash": "email_hash",
            "phone": "phone",
            "name": "name",
            "hash": "email_hash",
            "external_id": "external_id",
            "stable_reference": "user_id",
        }
        return sorted({mapping.get(kind, kind) for kind in matched})

    def discover(self, subject: SubjectGraph, as_of: datetime) -> list[ResourceRef]:
        if not self.root.exists():
            return []
        resources: list[ResourceRef] = []
        count = 0
        for current, dirnames, filenames in os.walk(self.root):
            dirnames[:] = sorted(
                name
                for name in dirnames
                if name not in {".git", ".venv", "node_modules", "__pycache__", ".erasureproof"}
                and (self.include_hidden or not name.startswith("."))
            )
            for filename in sorted(filenames):
                if filename.startswith(".") and not self.include_hidden:
                    continue
                path = Path(current) / filename
                if path.is_symlink():
                    continue
                try:
                    modified = datetime.fromtimestamp(path.stat().st_mtime, tz=as_of.tzinfo)
                except OSError:
                    continue
                if modified > as_of:
                    continue
                relative = path.relative_to(self.root).as_posix()
                count += 1
                if count > self.max_files:
                    break
                try:
                    with path.open("rb") as handle:
                        raw = handle.read(self.limits.max_bytes)
                    document = extract_file(path, limits=self.limits)
                except OSError:
                    continue
                combined = document.text
                if document.metadata:
                    combined = f"{combined}\n{metadata_text(document.metadata)}"
                found = extract_identifiers(combined)
                matched = _match_values(found, subject, self.names, combined)
                if not matched:
                    continue

                evidence_id = ""
                if self.evidence_store is not None:
                    evidence_id = self.evidence_store.put(
                        raw,
                        source=f"{self.system_id}:{relative}",
                        captured_at=datetime.now(tz=as_of.tzinfo),
                        content_type=str(document.metadata.get("mime", "application/octet-stream")),
                    ).evidence_id

                resources.append(
                    ResourceRef(
                        system_id=self.system_id,
                        resource_id=relative,
                        category=self._category_for(relative),
                        connector_id=self.connector_id,
                        payload={
                            "path": relative,
                            "size": len(raw),
                            "sha256": sha256_hex(raw),
                            "mime": document.metadata.get("mime"),
                            "matched": matched,
                            "subject_values": sorted(
                                {
                                    value
                                    for kind, values in matched.items()
                                    if kind != "stable_reference"
                                    for value in values
                                }
                            ),
                            "stable_reference": subject.user_id,
                            "ocr_used": document.ocr_used,
                            "redacted": False,
                        },
                        exposed_fields=self._exposed_fields(matched),
                        evidence_id=evidence_id,
                    )
                )
            if count > self.max_files:
                break
        return resources

    def remediate(
        self,
        ref: ResourceRef,
        action: Action,
        fields: tuple[str, ...] = (),
    ) -> ActionResult:
        relative = str(ref.payload.get("path", ref.resource_id))
        path = self._safe_path(relative)
        if path is None or not path.exists():
            return ActionResult(
                self.system_id, ref.resource_id, action.value, False, detail="file not found"
            )

        if action is Action.DELETE:
            path.unlink(missing_ok=True)
            return ActionResult(self.system_id, ref.resource_id, action.value, success=True)

        if action not in (Action.REDACT, Action.TOMBSTONE, Action.ANONYMIZE):
            return ActionResult(
                self.system_id,
                ref.resource_id,
                action.value,
                success=False,
                supported=False,
                detail="unsupported filesystem action",
            )

        suffix = path.suffix.lower()
        if suffix not in {
            ".txt",
            ".log",
            ".md",
            ".json",
            ".jsonl",
            ".csv",
            ".tsv",
            ".xml",
            ".html",
            ".htm",
            ".yaml",
            ".yml",
            ".ini",
            ".cfg",
            ".conf",
            ".sql",
            ".eml",
            ".py",
            ".js",
            ".ts",
            ".sh",
        }:
            return ActionResult(
                self.system_id,
                ref.resource_id,
                action.value,
                success=False,
                detail="binary or media file cannot be redacted safely; delete it instead",
            )

        values = [str(value) for value in ref.payload.get("subject_values", [])]
        try:
            raw = path.read_bytes()
            text = raw.decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            return ActionResult(
                self.system_id, ref.resource_id, action.value, False, detail=str(exc)
            )
        import re

        for value in sorted(set(values), key=len, reverse=True):
            if not value:
                continue
            anonymized = action is Action.ANONYMIZE
            replacement = "anon_" + sha256_hex(value)[:12] if anonymized else "[redacted]"
            text = re.sub(re.escape(value), replacement, text, flags=re.IGNORECASE)
        try:
            path.write_text(text, encoding="utf-8")
        except OSError as exc:
            return ActionResult(
                self.system_id, ref.resource_id, action.value, False, detail=str(exc)
            )
        return ActionResult(self.system_id, ref.resource_id, action.value, success=True)

    def verify(self, ref: ResourceRef, expected: State) -> VerificationResult:
        relative = str(ref.payload.get("path", ref.resource_id))
        path = self._safe_path(relative)
        exists = path is not None and path.exists()

        if expected is State.ABSENT:
            operation = VerificationOperation.VERIFY_RECORD_ABSENT
            actual = State.PRESENT if exists else State.ABSENT
        elif expected is State.PRESENT:
            operation = VerificationOperation.VERIFY_RECORD_PRESENT
            actual = State.PRESENT if exists else State.ABSENT
        elif not exists:
            operation = (
                VerificationOperation.VERIFY_RECORD_ANONYMIZED
                if expected is State.ANONYMIZED
                else VerificationOperation.VERIFY_RECORD_REDACTED
            )
            actual = State.ABSENT
        else:
            operation = (
                VerificationOperation.VERIFY_RECORD_ANONYMIZED
                if expected is State.ANONYMIZED
                else VerificationOperation.VERIFY_RECORD_REDACTED
            )
            document = extract_file(path, limits=self.limits)
            combined = f"{document.text}\n{metadata_text(document.metadata)}"
            found = extract_identifiers(combined)
            still_there = _contains_any(found, ref.payload.get("subject_values", []))
            if still_there:
                actual = State.PRESENT
            elif expected is State.ANONYMIZED:
                actual = State.ANONYMIZED
            else:
                actual = State.REDACTED

        return VerificationResult(
            operation=operation,
            system_id=self.system_id,
            resource_id=ref.resource_id,
            expected=expected,
            actual=actual,
            passed=actual is expected,
            evidence_id=ref.evidence_id,
        )


def _contains_any(found: dict[str, list[str]], values: list[Any]) -> bool:
    all_found = {str(value).lower() for values_ in found.values() for value in values_}
    for value in values:
        needle = str(value).strip().lower()
        if not needle:
            continue
        if needle in all_found:
            return True
        digits = "".join(ch for ch in needle if ch.isdigit())
        if len(digits) >= 7 and any(
            digits in "".join(ch for ch in candidate if ch.isdigit())
            for candidate in all_found
        ):
            return True
    return False


def _match_values(
    found: dict[str, list[str]],
    subject: SubjectGraph,
    names: list[str],
    text: str,
) -> dict[str, list[str]]:
    from ..intelligence.identifiers import match_subject

    return match_subject(found, subject, names, text)
