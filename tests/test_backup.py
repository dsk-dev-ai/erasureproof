from __future__ import annotations

import json
import sqlite3
import zipfile
from contextlib import closing
from pathlib import Path

import pytest

from erasureproof.backup import (
    BackupError,
    create_backup,
    restore_backup,
    verify_backup,
)
from erasureproof.config import Settings, get_settings
from erasureproof.evidence.store import EvidenceStore
from erasureproof.models.db import Tenant, get_database
from erasureproof.models.domain import utcnow


def _seed_state() -> tuple[str, str]:
    settings = get_settings()
    custom = Path(settings.data_dir) / "custom" / "state.json"
    custom.parent.mkdir(parents=True, exist_ok=True)
    custom.write_text('{"state": "original"}\n', encoding="utf-8")

    store = EvidenceStore(settings.evidence_dir)
    record = store.put(
        '{"email": "backup@example.com"}',
        source="test:backup",
        content_type="application/json",
    )
    with get_database().session() as session:
        session.add(
            Tenant(
                id="ten_backup",
                name="Backup Co",
                jurisdiction="gdpr",
                created_at=utcnow(),
            )
        )
    return record.evidence_id, str(custom)


def _alternate_settings(tmp_path: Path) -> Settings:
    return Settings(
        environment="development",
        data_dir=tmp_path / "restored",
        database_url=f"sqlite:///{tmp_path / 'restored' / 'erasureproof.db'}",
        policy_dir=get_settings().policy_dir,
        attestation_key=get_settings().attestation_key,
        demo_enabled=False,
    )


def test_backup_create_verify_and_restore(tmp_path) -> None:
    evidence_id, _custom = _seed_state()
    destination = tmp_path / "backup.zip"

    created = create_backup(destination)
    assert created["files"] >= 3
    assert created["database_included"] is True
    assert destination.stat().st_mode & 0o777 == 0o600

    verification = verify_backup(destination)
    assert verification.valid, verification.errors
    assert verification.manifest["signature"]["algorithm"] == "HMAC-SHA256"

    target = _alternate_settings(tmp_path)
    conflict = Path(target.data_dir) / "custom" / "state.json"
    conflict.parent.mkdir(parents=True, exist_ok=True)
    conflict.write_text("conflict\n", encoding="utf-8")
    with pytest.raises(BackupError, match="refusing to overwrite"):
        restore_backup(destination, settings=target)

    restored = restore_backup(destination, settings=target, force=True)
    assert restored["files"] >= 3
    assert Path(target.data_dir, "custom", "state.json").read_text() == '{"state": "original"}\n'
    assert (Path(target.data_dir) / "last-restore.json").exists()

    target_store = EvidenceStore(target.evidence_dir)
    assert target_store.get(evidence_id).startswith(b'{"email"')
    assert target_store.verify(evidence_id) is True

    with closing(sqlite3.connect(target.database_url.removeprefix("sqlite:///"))) as db:
        row = db.execute("SELECT name FROM tenants WHERE id = 'ten_backup'").fetchone()
    assert row == ("Backup Co",)


def test_backup_detects_tampering_and_destination_inside_data(tmp_path) -> None:
    _seed_state()
    destination = tmp_path / "backup.zip"
    create_backup(destination)

    with zipfile.ZipFile(destination) as archive:
        members = {name: archive.read(name) for name in archive.namelist()}
    manifest = json.loads(members["manifest.json"])
    first = next(item for item in manifest["files"] if item["kind"] == "data")
    members[first["arcname"]] = members[first["arcname"]] + b"tampered"
    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(tampered, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)

    verification = verify_backup(tampered)
    assert verification.valid is False
    assert any("mismatch" in error for error in verification.errors)
    with pytest.raises(BackupError, match="verification failed"):
        restore_backup(tampered, settings=_alternate_settings(tmp_path))

    with pytest.raises(BackupError, match="outside the live data"):
        create_backup(Path(get_settings().data_dir) / "backup.zip")


def test_backup_rejects_a_wrong_signing_key(tmp_path) -> None:
    _seed_state()
    destination = tmp_path / "backup.zip"
    create_backup(destination)
    other = get_settings().model_copy(update={"attestation_key": "different-key"})
    verification = verify_backup(destination, settings=other)
    assert verification.valid is False
    assert "manifest signature is invalid" in verification.errors
