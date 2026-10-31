"""Object-store connector for exports, attachments, archives and logs.

Supports an S3-compatible bucket (``backend: s3``) and a local directory
(``backend: local``) so the demo runs without cloud credentials. Documents are
matched by scanning their contents for any known identifier.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..canonical import sha256_hex
from ..models.domain import (
    Action,
    ActionResult,
    Category,
    IdentifierType,
    ResourceRef,
    State,
    SubjectGraph,
    VerificationOperation,
    VerificationResult,
)
from .base import BaseConnector

_TYPE_FIELD = {
    IdentifierType.EMAIL: "email",
    IdentifierType.PHONE: "phone",
    IdentifierType.EMAIL_HASH: "email_hash",
    IdentifierType.EXTERNAL_ID: "external_id",
}


class S3Connector(BaseConnector):
    type = "s3"
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
        self.backend = str(self.config.get("backend", "local")).lower()
        self.root = Path(self.config.get("root", "./.erasureproof/bucket")).expanduser().resolve()
        self.bucket = self.config.get("bucket")
        self.prefix = str(self.config.get("prefix", ""))
        self.categories = {
            str(key): Category(str(value).upper())
            for key, value in (self.config.get("categories") or {}).items()
        }
        self.default_category = Category(
            str(self.config.get("default_category", "EXPORT")).upper()
        )
        self.max_bytes = int(self.config.get("max_bytes", 2_000_000))
        self._client = None

    # -- backend helpers ---------------------------------------------------

    def _s3(self):
        if self._client is None:
            import boto3  # type: ignore

            self._client = boto3.client("s3", **self.config.get("client", {}))
        return self._client

    def _local_path(self, key: str) -> Path:
        candidate = (self.root / key).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise ValueError(f"object path escapes connector root: {key!r}") from exc
        return candidate

    def _entries(self) -> list[tuple[str, datetime]]:
        if self.backend == "s3":
            if not self.bucket:
                raise ValueError("S3 connector requires a 'bucket'")
            paginator = self._s3().get_paginator("list_objects_v2")
            entries = []
            for page in paginator.paginate(Bucket=self.bucket, Prefix=self.prefix):
                for item in page.get("Contents", []):
                    entries.append((item["Key"], item["LastModified"]))
            return entries

        if not self.root.exists():
            return []
        entries = []
        for path in sorted(self.root.rglob("*")):
            if path.is_symlink() or not path.is_file():
                continue
            try:
                path.resolve().relative_to(self.root)
            except ValueError:
                continue
            relative = path.relative_to(self.root).as_posix()
            if self.prefix and not relative.startswith(self.prefix):
                continue
            entries.append(
                (relative, datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc))
            )
        return entries

    def _read(self, key: str) -> bytes:
        if self.backend == "s3":
            response = self._s3().get_object(Bucket=self.bucket, Key=key)
            return response["Body"].read(self.max_bytes)
        return self._local_path(key).read_bytes()[: self.max_bytes]

    def _write(self, key: str, data: bytes) -> None:
        if self.backend == "s3":
            self._s3().put_object(Bucket=self.bucket, Key=key, Body=data)
            return
        path = self._local_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def _delete(self, key: str) -> None:
        if self.backend == "s3":
            self._s3().delete_object(Bucket=self.bucket, Key=key)
            return
        self._local_path(key).unlink(missing_ok=True)

    # -- discovery ---------------------------------------------------------

    def _category_for(self, key: str) -> Category:
        matches = [
            (prefix, category)
            for prefix, category in self.categories.items()
            if key.startswith(prefix)
        ]
        if not matches:
            return self.default_category
        return max(matches, key=lambda item: len(item[0]))[1]

    @staticmethod
    def _decode(raw: bytes) -> str:
        return raw.decode("utf-8", errors="ignore")

    @staticmethod
    def _matched_identifiers(text: str, subject: SubjectGraph) -> list[IdentifierType]:
        lowered = text.lower()
        digits = "".join(ch for ch in text if ch.isdigit())
        matched: list[IdentifierType] = []
        for identifier in subject.identifiers:
            kind = identifier.type
            if kind is IdentifierType.PHONE:
                hit = identifier.normalized().lstrip("+") in digits
            else:
                raw = identifier.value.strip().lower()
                hit = bool(raw) and (raw in lowered or identifier.normalized() in lowered)
            if hit and kind not in matched:
                matched.append(kind)
        return matched

    def discover(self, subject: SubjectGraph, as_of: datetime) -> list[ResourceRef]:
        resources: list[ResourceRef] = []
        for key, modified in self._entries():
            if modified > as_of:
                continue
            try:
                raw = self._read(key)
            except (FileNotFoundError, OSError):
                continue
            text = self._decode(raw)
            matched = self._matched_identifiers(text, subject)
            if not matched:
                continue

            evidence_id = self._record_evidence(
                raw,
                source=f"{self.system_id}:{key}",
                captured_at=modified,
            )
            raw_values = [
                identifier.value
                for identifier in subject.identifiers
                if identifier.type in matched
            ]
            payload = {
                "path": key,
                "size": len(raw),
                "content_hash": sha256_hex(raw),
                "matched_identifier_types": [kind.value for kind in matched],
                "backend": self.backend,
                "_subject_values": raw_values,
            }
            resources.append(
                ResourceRef(
                    system_id=self.system_id,
                    resource_id=key,
                    category=self._category_for(key),
                    connector_id=self.connector_id,
                    payload=payload,
                    exposed_fields=[_TYPE_FIELD[kind] for kind in matched],
                    evidence_id=evidence_id,
                )
            )
        return resources

    # -- remediation -------------------------------------------------------

    def remediate(
        self,
        ref: ResourceRef,
        action: Action,
        fields: tuple[str, ...] = (),
    ) -> ActionResult:
        key = str(ref.payload.get("path", ref.resource_id))
        try:
            if action is Action.DELETE:
                self._delete(key)
                return ActionResult(self.system_id, ref.resource_id, action.value, success=True)

            if action not in (Action.REDACT, Action.TOMBSTONE, Action.ANONYMIZE):
                return ActionResult(
                    self.system_id,
                    ref.resource_id,
                    action.value,
                    success=False,
                    supported=False,
                )

            raw = self._read(key)
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                return ActionResult(
                    self.system_id,
                    ref.resource_id,
                    action.value,
                    success=False,
                    detail="binary object cannot be redacted safely; delete it instead",
                )

            values = [str(value) for value in ref.payload.get("_subject_values", [])]
            for value in sorted(set(values), key=len, reverse=True):
                if not value:
                    continue
                if action is Action.ANONYMIZE:
                    replacement = "anon_" + sha256_hex(value)[:12]
                else:
                    replacement = "[redacted]"
                text = re.sub(re.escape(value), replacement, text, flags=re.IGNORECASE)

            self._write(key, text.encode("utf-8"))
            return ActionResult(self.system_id, ref.resource_id, action.value, success=True)
        except Exception as exc:  # pragma: no cover - backend defensive
            return ActionResult(
                self.system_id, ref.resource_id, action.value, success=False, detail=str(exc)
            )

    def _exists(self, key: str) -> bool:
        if self.backend == "s3":
            try:
                self._s3().head_object(Bucket=self.bucket, Key=key)
                return True
            except Exception:
                return False
        try:
            return self._local_path(key).exists()
        except ValueError:
            return False

    def snapshot(self, ref: ResourceRef, as_of: datetime | None = None) -> bytes:
        return self._read(str(ref.payload.get("path", ref.resource_id)))

    def verify(self, ref: ResourceRef, expected: State) -> VerificationResult:
        key = str(ref.payload.get("path", ref.resource_id))
        exists = self._exists(key)

        if expected is State.ABSENT:
            operation = VerificationOperation.VERIFY_RECORD_ABSENT
            actual = State.PRESENT if exists else State.ABSENT
        elif expected is State.PRESENT:
            operation = VerificationOperation.VERIFY_RECORD_PRESENT
            actual = State.PRESENT if exists else State.ABSENT
        else:
            operation = (
                VerificationOperation.VERIFY_RECORD_ANONYMIZED
                if expected is State.ANONYMIZED
                else VerificationOperation.VERIFY_RECORD_REDACTED
            )
            if not exists:
                actual = State.ABSENT
            else:
                text = self._decode(self._read(key)).lower()
                values = [
                    str(value).lower()
                    for value in ref.payload.get("_subject_values", [])
                    if value
                ]
                still_present = any(value in text for value in values)
                if still_present:
                    actual = State.PRESENT
                elif expected is State.ANONYMIZED and "anon_" in text:
                    actual = State.ANONYMIZED
                elif expected is State.REDACTED:
                    actual = State.REDACTED
                else:
                    actual = State.PRESENT

        return VerificationResult(
            operation=operation,
            system_id=self.system_id,
            resource_id=ref.resource_id,
            expected=expected,
            actual=actual,
            passed=actual is expected,
            evidence_id=ref.evidence_id,
        )


class LocalObjectConnector(S3Connector):
    type = "local"

    def __init__(
        self,
        connector_id: str,
        system_id: str,
        config: dict[str, Any] | None = None,
        evidence_store: Any | None = None,
    ) -> None:
        config = dict(config or {})
        config.setdefault("backend", "local")
        super().__init__(connector_id, system_id, config, evidence_store)
