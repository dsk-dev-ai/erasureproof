"""Content-addressed evidence store.

Every snapshot is immutable: files are stored under their SHA-256, and metadata
records when and where the evidence was captured. Identical content is stored
once, which keeps audits cheap without weakening provenance.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from ..canonical import canonical_json, sha256_hex


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    evidence_id: str
    sha256: str
    path: str
    source: str
    captured_at: datetime
    size: int
    content_type: str = "application/octet-stream"
    request_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "sha256": self.sha256,
            "path": self.path,
            "source": self.source,
            "captured_at": self.captured_at.isoformat(),
            "size": self.size,
            "content_type": self.content_type,
            "request_id": self.request_id,
        }


class EvidenceStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.objects = self.root / "objects"
        self.meta = self.root / "meta"
        self.objects.mkdir(parents=True, exist_ok=True)
        self.meta.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _as_bytes(content: bytes | str | dict | list) -> tuple[bytes, str]:
        if isinstance(content, bytes):
            return content, "application/octet-stream"
        if isinstance(content, str):
            return content.encode("utf-8"), "text/plain; charset=utf-8"
        return canonical_json(content).encode("utf-8"), "application/json"

    def put(
        self,
        content: bytes | str | dict | list,
        source: str,
        captured_at: datetime | None = None,
        request_id: str | None = None,
        content_type: str | None = None,
    ) -> EvidenceRecord:
        raw, detected_type = self._as_bytes(content)
        digest = sha256_hex(raw)
        evidence_id = f"ev_{digest[:24]}"
        captured_at = captured_at or datetime.now(timezone.utc)
        if captured_at.tzinfo is None:
            captured_at = captured_at.replace(tzinfo=timezone.utc)

        object_dir = self.objects / digest[:2]
        object_dir.mkdir(parents=True, exist_ok=True)
        object_path = object_dir / digest
        if not object_path.exists():
            with NamedTemporaryFile("wb", dir=object_dir, delete=False) as handle:
                handle.write(raw)
                temp_path = handle.name
            os.replace(temp_path, object_path)

        meta_path = self.meta / f"{evidence_id}.json"
        metadata = {
            "evidence_id": evidence_id,
            "sha256": digest,
            "path": str(object_path),
            "source": source,
            "captured_at": captured_at.isoformat(),
            "size": len(raw),
            "content_type": content_type or detected_type,
            "request_id": request_id,
        }
        meta_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

        return EvidenceRecord(
            evidence_id=evidence_id,
            sha256=digest,
            path=str(object_path),
            source=source,
            captured_at=captured_at,
            size=len(raw),
            content_type=metadata["content_type"],
            request_id=request_id,
        )

    def metadata(self, evidence_id: str) -> dict[str, Any]:
        meta_path = self.meta / f"{evidence_id}.json"
        if not meta_path.exists():
            raise FileNotFoundError(f"Unknown evidence: {evidence_id}")
        return json.loads(meta_path.read_text(encoding="utf-8"))

    def get(self, evidence_id: str) -> bytes:
        metadata = self.metadata(evidence_id)
        return Path(metadata["path"]).read_bytes()

    def exists(self, evidence_id: str) -> bool:
        return (self.meta / f"{evidence_id}.json").exists()

    def verify(self, evidence_id: str) -> bool:
        metadata = self.metadata(evidence_id)
        raw = Path(metadata["path"]).read_bytes()
        return sha256_hex(raw) == metadata["sha256"]
