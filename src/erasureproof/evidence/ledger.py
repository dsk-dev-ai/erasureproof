"""Append-only audit ledger with a SHA-256 hash chain.

Each entry commits to the previous entry's hash, so deleting or editing history
is detectable. Entries are JSONL, one write per line, fsynced for durability.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..canonical import canonical_json, sha256_hex

GENESIS = "0" * 64
_APPEND_LOCK = threading.Lock()


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    seq: int
    timestamp: str
    event: str
    request_id: str
    payload: dict[str, Any]
    prev_hash: str
    hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "timestamp": self.timestamp,
            "event": self.event,
            "request_id": self.request_id,
            "payload": self.payload,
            "prev_hash": self.prev_hash,
            "hash": self.hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LedgerEntry:
        return cls(
            seq=int(data["seq"]),
            timestamp=str(data["timestamp"]),
            event=str(data["event"]),
            request_id=str(data.get("request_id", "")),
            payload=dict(data.get("payload") or {}),
            prev_hash=str(data["prev_hash"]),
            hash=str(data["hash"]),
        )

    def preimage(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "timestamp": self.timestamp,
            "event": self.event,
            "request_id": self.request_id,
            "payload": self.payload,
            "prev_hash": self.prev_hash,
        }


def _entry_hash(entry: LedgerEntry) -> str:
    return sha256_hex(canonical_json(entry.preimage()))


class EvidenceLedger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch()

    def read(self) -> list[LedgerEntry]:
        entries: list[LedgerEntry] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                entries.append(LedgerEntry.from_dict(json.loads(line)))
        return entries

    def head(self) -> str:
        entries = self.read()
        return entries[-1].hash if entries else GENESIS

    def append(
        self,
        event: str,
        request_id: str = "",
        payload: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> LedgerEntry:
        with _APPEND_LOCK:
            entries = self.read()
            prev_hash = entries[-1].hash if entries else GENESIS
            timestamp = timestamp or datetime.now(timezone.utc)
            entry = LedgerEntry(
                seq=len(entries) + 1,
                timestamp=timestamp.isoformat(),
                event=event,
                request_id=request_id,
                payload=payload or {},
                prev_hash=prev_hash,
                hash="",
            )
            entry = LedgerEntry(
                seq=entry.seq,
                timestamp=entry.timestamp,
                event=entry.event,
                request_id=entry.request_id,
                payload=entry.payload,
                prev_hash=entry.prev_hash,
                hash=_entry_hash(entry),
            )
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            return entry

    def verify(self) -> tuple[bool, str]:
        entries = self.read()
        prev_hash = GENESIS
        for index, entry in enumerate(entries, start=1):
            if entry.seq != index:
                return False, f"entry {index} has seq {entry.seq}"
            if entry.prev_hash != prev_hash:
                return False, f"entry {index} has broken prev_hash"
            if _entry_hash(entry) != entry.hash:
                return False, f"entry {index} hash mismatch"
            prev_hash = entry.hash
        return True, f"ok ({len(entries)} entries)"
