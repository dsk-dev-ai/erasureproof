"""Relational connector.

Works with SQLite, Postgres, MySQL and anything SQLAlchemy speaks. Table and
column names come from trusted connector configuration and are validated before
being interpolated; values are always bound parameters.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, inspect, text

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
    normalize_value,
)
from .base import BaseConnector

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_DEFAULT_PII = ("name", "email", "phone", "email_hash")


def _safe(name: str) -> str:
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(f"Unsafe SQL identifier: {name!r}")
    return name


def _jsonable(row: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, datetime):
            result[key] = value.isoformat()
        elif isinstance(value, (bytes, bytearray)):
            result[key] = value.decode("utf-8", errors="replace")
        else:
            result[key] = value
    return result


class SQLConnector(BaseConnector):
    type = "sql"
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
        url = self.config.get("url")
        if not url:
            raise ValueError("SQL connector requires a 'url'")
        self.engine = create_engine(url, future=True)
        self.tables: dict[str, dict[str, Any]] = self.config.get("tables", {})

    def close(self) -> None:
        self.engine.dispose()

    def _columns(self, table: str) -> list[str]:
        return [column["name"] for column in inspect(self.engine).get_columns(table)]

    def _select_all(self, table: str) -> list[dict[str, Any]]:
        _safe(table)
        with self.engine.connect() as connection:
            rows = connection.execute(text(f"SELECT * FROM {_safe(table)}")).mappings().all()
        return [dict(row) for row in rows]

    def _select_one(self, table: str, pk: str, value: Any) -> dict[str, Any] | None:
        _safe(table)
        _safe(pk)
        with self.engine.connect() as connection:
            row = (
                connection.execute(
                    text(f"SELECT * FROM {_safe(table)} WHERE {_safe(pk)} = :pk"),
                    {"pk": value},
                )
                .mappings()
                .first()
            )
        return dict(row) if row else None

    @staticmethod
    def _identifier_columns(
        spec: dict[str, Any], row: dict[str, Any]
    ) -> list[tuple[str, IdentifierType]]:
        configured = spec.get("subject_columns")
        if configured:
            return [(column, IdentifierType(str(kind).upper())) for column, kind in configured]
        inferred = []
        for column in ("email", "phone", "email_hash"):
            if column in row:
                inferred.append((column, IdentifierType(column.upper())))
        return inferred

    def _matches(self, spec: dict[str, Any], row: dict[str, Any], subject: SubjectGraph) -> bool:
        user_id_column = spec.get("user_id_column")
        if user_id_column is None and "user_id" in row:
            user_id_column = "user_id"
        if (
            user_id_column
            and subject.user_id
            and str(row.get(user_id_column)) == subject.user_id
        ):
            return True

        values = subject.values()
        for column, kind in self._identifier_columns(spec, row):
            raw = row.get(column)
            if raw is None:
                continue
            if normalize_value(str(raw), kind) in values:
                return True
        return False

    @staticmethod
    def _pii_fields(spec: dict[str, Any], row: dict[str, Any]) -> list[str]:
        configured = spec.get("pii_fields")
        if configured:
            return [field for field in configured if field in row]
        return [field for field in _DEFAULT_PII if field in row]

    @staticmethod
    def _exposed(row: dict[str, Any], pii_fields: list[str]) -> list[str]:
        exposed = []
        for field in pii_fields:
            value = row.get(field)
            if value not in (None, "", "[redacted]", "ANONYMIZED"):
                exposed.append(field)
        return exposed

    def discover(self, subject: SubjectGraph, as_of: datetime) -> list[ResourceRef]:
        resources: list[ResourceRef] = []

        for table, spec in self.tables.items():
            _safe(table)
            pk = str(spec.get("pk") or spec.get("id_column") or "id")
            timestamp_column = spec.get("timestamp_column")
            for row in self._select_all(table):
                if timestamp_column:
                    raw_timestamp = row.get(timestamp_column)
                    if isinstance(raw_timestamp, datetime):
                        when = raw_timestamp
                        if when.tzinfo is None:
                            when = when.replace(tzinfo=timezone.utc)
                        if when > as_of:
                            continue
                if not self._matches(spec, row, subject):
                    continue

                pk_value = row.get(pk)
                resource_id = f"{table}:{pk_value}"
                pii = self._pii_fields(spec, row)
                payload = _jsonable(row)
                payload.update({"_table": table, "_pk": pk, "_pk_value": pk_value})
                flag = spec.get("anonymized_column")
                if (flag and bool(row.get(flag))) or (
                    pii
                    and all(str(row.get(field, "")).startswith("anon_") for field in pii)
                ):
                    payload["anonymized"] = True
                evidence_id = self._record_evidence(
                    payload,
                    source=f"{self.system_id}:{table}",
                    captured_at=as_of,
                )
                resources.append(
                    ResourceRef(
                        system_id=self.system_id,
                        resource_id=resource_id,
                        category=Category(str(spec.get("category", "PRIMARY_ACCOUNT")).upper()),
                        connector_id=self.connector_id,
                        payload=payload,
                        exposed_fields=self._exposed(row, pii),
                        evidence_id=evidence_id,
                    )
                )

        return resources

    def remediate(
        self,
        ref: ResourceRef,
        action: Action,
        fields: tuple[str, ...] = (),
    ) -> ActionResult:
        table = str(ref.payload.get("_table", ""))
        pk = str(ref.payload.get("_pk", "id"))
        pk_value = ref.payload.get("_pk_value")
        spec = self.tables.get(table, {})
        pii = [field for field in self._pii_fields(spec, ref.payload)]

        try:
            _safe(table)
            _safe(pk)
            with self.engine.begin() as connection:
                if action is Action.DELETE:
                    connection.execute(
                        text(f"DELETE FROM {_safe(table)} WHERE {_safe(pk)} = :pk"),
                        {"pk": pk_value},
                    )
                elif action in (Action.REDACT, Action.TOMBSTONE):
                    columns = [field for field in (fields or tuple(pii)) if field in pii]
                    if not columns:
                        return ActionResult(
                            self.system_id,
                            ref.resource_id,
                            action.value,
                            success=True,
                            detail="no identifying fields required removal",
                        )
                    assignments = ", ".join(f"{_safe(column)} = NULL" for column in columns)
                    connection.execute(
                        text(
                            f"UPDATE {_safe(table)} SET {assignments} "
                            f"WHERE {_safe(pk)} = :pk"
                        ),
                        {"pk": pk_value},
                    )
                elif action is Action.ANONYMIZE:
                    assignments = []
                    params: dict[str, Any] = {"pk": pk_value}
                    for column in pii:
                        token = "anon_" + sha256_hex(f"{pk_value}:{column}")[:12]
                        assignments.append(f"{_safe(column)} = :{column}")
                        params[column] = token
                    flag = spec.get("anonymized_column")
                    if flag:
                        assignments.append(f"{_safe(flag)} = :anonymized")
                        params["anonymized"] = True
                    connection.execute(
                        text(
                            f"UPDATE {_safe(table)} SET {', '.join(assignments)} "
                            f"WHERE {_safe(pk)} = :pk"
                        ),
                        params,
                    )
                else:
                    return ActionResult(
                        self.system_id,
                        ref.resource_id,
                        action.value,
                        success=False,
                        supported=False,
                        detail=f"unsupported action {action.value}",
                    )
        except Exception as exc:  # pragma: no cover - defensive
            return ActionResult(
                self.system_id,
                ref.resource_id,
                action.value,
                success=False,
                detail=str(exc),
            )

        return ActionResult(self.system_id, ref.resource_id, action.value, success=True)

    def verify(self, ref: ResourceRef, expected: State) -> VerificationResult:
        table = str(ref.payload.get("_table", ""))
        pk = str(ref.payload.get("_pk", "id"))
        pk_value = ref.payload.get("_pk_value")
        row = self._select_one(table, pk, pk_value)

        if expected is State.ABSENT:
            actual = State.ABSENT if row is None else State.PRESENT
            operation = VerificationOperation.VERIFY_RECORD_ABSENT
        elif expected is State.REDACTED:
            if row is None:
                actual = State.ABSENT
            else:
                spec = self.tables.get(table, {})
                pii = self._pii_fields(spec, row)
                actual = State.REDACTED if not self._exposed(row, pii) else State.PRESENT
            operation = VerificationOperation.VERIFY_RECORD_REDACTED
        elif expected is State.ANONYMIZED:
            operation = VerificationOperation.VERIFY_RECORD_ANONYMIZED
            if row is None:
                actual = State.ABSENT
            else:
                spec = self.tables.get(table, {})
                pii = self._pii_fields(spec, row)
                flag = spec.get("anonymized_column")
                if flag and bool(row.get(flag)):
                    actual = State.ANONYMIZED
                elif pii and all(str(row.get(field, "")).startswith("anon_") for field in pii):
                    actual = State.ANONYMIZED
                else:
                    actual = State.PRESENT
        else:
            actual = State.PRESENT if row is not None else State.ABSENT
            operation = VerificationOperation.VERIFY_RECORD_PRESENT

        return VerificationResult(
            operation=operation,
            system_id=self.system_id,
            resource_id=ref.resource_id,
            expected=expected,
            actual=actual,
            passed=actual is expected,
            evidence_id=ref.evidence_id,
        )
