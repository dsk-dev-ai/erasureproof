"""Control-plane connector for sync jobs and backup restore points.

The control plane is a small JSON document supplied by the customer (or written
by an internal service). It lets the engine prove which pipelines can recreate
data and which backups can restore it — and then disable/block them.
"""

from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from ..models.domain import (
    ActionResult,
    BackupRef,
    FlowRef,
    IdentifierType,
    ResourceRef,
    SubjectGraph,
    normalize_value,
)
from .base import BaseConnector

_LOCK = threading.Lock()
_PHONE_RE = re.compile(r"[^0-9+]")


def _canonical(value: Any) -> str:
    text = str(value).strip()
    if "@" in text:
        return normalize_value(text, IdentifierType.EMAIL)
    digits = _PHONE_RE.sub("", text)
    if len(digits) >= 7:
        return digits
    return text.lower()


class ControlConnector(BaseConnector):
    type = "control"
    supports_flow_control = True
    supports_restore_control = True
    supports_remediation = False

    def __init__(
        self,
        connector_id: str,
        system_id: str,
        config: dict[str, Any] | None = None,
        evidence_store: Any | None = None,
    ) -> None:
        super().__init__(connector_id, system_id, config, evidence_store)
        path = self.config.get("path")
        if not path:
            raise ValueError("Control connector requires a 'path'")
        self.path = Path(path)

    def discover(self, subject: SubjectGraph, as_of: datetime) -> list[ResourceRef]:
        return []

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"flows": [], "backups": []}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            "w", encoding="utf-8", dir=self.path.parent, delete=False, suffix=".tmp"
        ) as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            temp_path = handle.name
        os.replace(temp_path, self.path)

    @staticmethod
    def _matches(entry: dict[str, Any], subject: SubjectGraph) -> bool:
        if subject.user_id and subject.user_id in {
            str(value) for value in entry.get("subject_ids", [])
        }:
            return True
        wanted = subject.values()
        for value in entry.get("subject_values", []):
            if _canonical(value) in wanted:
                return True
        return False

    def discover_flows(self, subject: SubjectGraph, as_of: datetime) -> list[FlowRef]:
        data = self._load()
        flows: list[FlowRef] = []
        for entry in data.get("flows", []):
            if not self._matches(entry, subject):
                continue
            flow = FlowRef(
                system_id=str(entry.get("system_id", self.system_id)),
                flow_id=str(entry["flow_id"]),
                source=str(entry.get("source", "")),
                dest=str(entry.get("dest", "")),
                status=str(entry.get("status", "ACTIVE")),
            )
            flow.evidence_id = self._record_evidence(
                entry, source=f"{self.system_id}:flow", captured_at=as_of
            )
            flows.append(flow)
        return flows

    def discover_backups(self, subject: SubjectGraph, as_of: datetime) -> list[BackupRef]:
        data = self._load()
        backups: list[BackupRef] = []
        for entry in data.get("backups", []):
            if not self._matches(entry, subject):
                continue
            backup = BackupRef(
                system_id=str(entry.get("system_id", self.system_id)),
                backup_id=str(entry["backup_id"]),
                restore_risk=bool(entry.get("restore_risk", True)),
            )
            backup.evidence_id = self._record_evidence(
                entry, source=f"{self.system_id}:backup", captured_at=as_of
            )
            backups.append(backup)
        return backups

    def disable_flow(self, flow: FlowRef) -> ActionResult:
        with _LOCK:
            data = self._load()
            for entry in data.get("flows", []):
                if str(entry.get("flow_id")) == flow.flow_id and str(
                    entry.get("system_id", self.system_id)
                ) == flow.system_id:
                    entry["status"] = "DISABLED"
                    entry["disabled_at"] = datetime.now(timezone.utc).isoformat()
                    self._save(data)
                    return ActionResult(
                        self.system_id, flow.flow_id, "DISABLE_DATA_FLOW", success=True
                    )
        return ActionResult(
            self.system_id,
            flow.flow_id,
            "DISABLE_DATA_FLOW",
            success=False,
            detail="flow not found in control plane",
        )

    def block_restore(self, backup: BackupRef) -> ActionResult:
        with _LOCK:
            data = self._load()
            for entry in data.get("backups", []):
                if str(entry.get("backup_id")) == backup.backup_id and str(
                    entry.get("system_id", self.system_id)
                ) == backup.system_id:
                    entry["restore_risk"] = False
                    entry["blocked_at"] = datetime.now(timezone.utc).isoformat()
                    self._save(data)
                    return ActionResult(
                        self.system_id, backup.backup_id, "BLOCK_RESTORE", success=True
                    )
        return ActionResult(
            self.system_id,
            backup.backup_id,
            "BLOCK_RESTORE",
            success=False,
            detail="backup not found in control plane",
        )
