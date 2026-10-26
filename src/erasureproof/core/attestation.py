"""Signed, tamper-evident deletion attestations.

An attestation binds the request outcome, the ordered plan and the verification
results into one canonical payload signed with HMAC-SHA256. Swap the signer for
KMS/Vault in production; the payload format stays the same.
"""

from __future__ import annotations

import hmac
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from ..canonical import canonical_json
from ..config import get_settings
from ..models.domain import Attestation, Plan, VerificationResult

ATTESTATION_VERSION = "1"


def sign_payload(payload: dict[str, Any], key: str) -> str:
    return hmac.new(
        key.encode("utf-8"),
        canonical_json(payload).encode("utf-8"),
        "sha256",
    ).hexdigest()


def verify_signature(payload: dict[str, Any], signature: str, key: str) -> bool:
    expected = sign_payload(payload, key)
    return hmac.compare_digest(expected, signature)


class AttestationService:
    def __init__(self, key: str, directory: str | Path) -> None:
        self.key = key
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_settings(cls) -> AttestationService:
        settings = get_settings()
        return cls(
            settings.attestation_key,
            settings.attestation_dir or ".erasureproof/attestations",
        )

    def build_payload(
        self,
        request_id: str,
        status: str,
        plan: Plan | None = None,
        verifications: list[VerificationResult] | None = None,
        ledger_head: str = "",
        issued_at: datetime | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        issued_at = issued_at or datetime.now(timezone.utc)
        steps = plan.steps if plan else []
        payload: dict[str, Any] = {
            "attestation_version": ATTESTATION_VERSION,
            "request_id": request_id,
            "status": status,
            "issued_at": issued_at.isoformat(),
            "ledger_head": ledger_head,
            "summary": {
                "step_count": len(steps),
                "finding_count": sum(1 for s in steps if s.phase.value == "FINDING"),
                "verification_count": sum(1 for s in steps if s.phase.value == "VERIFICATION"),
                "verifications_passed": (
                    all(v.passed for v in verifications) if verifications else None
                ),
            },
            "plan": plan.to_dict() if plan else None,
            "verifications": [v.to_dict() for v in (verifications or [])],
        }
        if extra:
            payload["extra"] = extra
        return payload

    def issue(
        self,
        request_id: str,
        status: str,
        plan: Plan | None = None,
        verifications: list[VerificationResult] | None = None,
        ledger_head: str = "",
        issued_at: datetime | None = None,
        extra: dict[str, Any] | None = None,
    ) -> Attestation:
        payload = self.build_payload(
            request_id,
            status,
            plan=plan,
            verifications=verifications,
            ledger_head=ledger_head,
            issued_at=issued_at,
            extra=extra,
        )
        signature = sign_payload(payload, self.key)

        destination = self.directory / f"{request_id}.attestation.json"
        document = {"payload": payload, "signature": signature}
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=self.directory,
            delete=False,
            suffix=".tmp",
        ) as handle:
            json.dump(document, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            temp_path = handle.name
        os.replace(temp_path, destination)

        return Attestation(
            request_id=request_id,
            status=status,
            issued_at=datetime.fromisoformat(payload["issued_at"]),
            payload=payload,
            signature=signature,
            path=str(destination),
        )

    def verify(self, payload: dict[str, Any], signature: str) -> bool:
        return verify_signature(payload, signature, self.key)

    def verify_file(self, path: str | Path) -> tuple[bool, dict[str, Any]]:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
        payload = document.get("payload", {})
        signature = document.get("signature", "")
        return self.verify(payload, signature), payload
