"""Verified backup and restore for ErasureProof state.

SQLite databases are copied with the SQLite backup API so a consistent snapshot
is captured while the service is online. PostgreSQL deployments should use
``pg_dump``/``pg_restore`` for the metadata database and this tool for evidence,
ledger, and attestations.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from sqlalchemy.engine import make_url

from . import __version__
from .config import Settings, get_settings
from .core.attestation import sign_payload, verify_signature

FORMAT = "erasureproof-backup"
FORMAT_VERSION = 1
MANIFEST = "manifest.json"
CHUNK = 1024 * 1024
MAX_MANIFEST_BYTES = 16 * 1024 * 1024
KINDS = {"data", "evidence", "attestations", "ledger", "database"}


class BackupError(RuntimeError):
    """A backup could not be created, verified, or restored safely."""


@dataclass(frozen=True)
class BackupFile:
    arcname: str
    kind: str
    path: str
    size: int
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "arcname": self.arcname,
            "kind": self.kind,
            "path": self.path,
            "size": self.size,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class BackupVerification:
    valid: bool
    errors: list[str]
    manifest: dict[str, Any] | None
    path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": self.errors,
            "path": str(self.path),
            "created_at": (self.manifest or {}).get("created_at"),
            "files": len((self.manifest or {}).get("files", [])),
        }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_stream(handle, limit: int | None = None) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    while True:
        if limit is None:
            chunk = handle.read(CHUNK)
        else:
            chunk = handle.read(min(CHUNK, limit + 1 - size))
        if not chunk:
            break
        digest.update(chunk)
        size += len(chunk)
        if limit is not None and size > limit:
            break
    return digest.hexdigest(), size


def _safe_member(value: str) -> bool:
    if not value or "\\" in value or value.startswith("/"):
        return False
    path = PurePosixPath(value)
    return all(part not in {"", ".", ".."} for part in path.parts)


def _under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _database_path(settings: Settings) -> Path | None:
    if not settings.is_sqlite:
        return None
    database = make_url(settings.database_url).database
    if not database or database == ":memory:":
        return None
    return Path(database).expanduser().resolve()


def _sqlite_snapshot(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise BackupError(f"SQLite database does not exist: {source}")
    with (
        closing(sqlite3.connect(source)) as origin,
        closing(sqlite3.connect(destination)) as target,
    ):
        origin.backup(target)


def _walk(root: Path, kind: str) -> list[tuple[Path, str, str]]:
    if not root.exists():
        return []
    items: list[tuple[Path, str, str]] = []
    for current, directories, files in os.walk(root):
        directories.sort()
        for filename in sorted(files):
            path = Path(current) / filename
            if path.is_symlink() or not path.is_file():
                continue
            if filename in {".DS_Store"}:
                continue
            relative = path.relative_to(root).as_posix()
            items.append((path, kind, relative))
    return items


def _source_files(
    settings: Settings, database: Path | None, destination: Path
) -> list[tuple[Path, str, str]]:
    data_root = Path(settings.data_dir).resolve()
    roots: list[tuple[Path, str]] = [(data_root, "data")]
    for root, kind in (
        (Path(settings.evidence_dir or data_root / "evidence").resolve(), "evidence"),
        (Path(settings.attestation_dir or data_root / "attestations").resolve(), "attestations"),
    ):
        if not any(_under(root, existing) for existing, _ in roots):
            roots.append((root, kind))

    selected: list[tuple[Path, str, str]] = []
    seen: set[Path] = set()
    for root, kind in roots:
        for path, _, relative in _walk(root, kind):
            resolved = path.resolve()
            if resolved in seen or _under(resolved, destination):
                continue
            if database is not None and resolved in {
                database,
                Path(f"{database}-wal"),
                Path(f"{database}-shm"),
            }:
                continue
            seen.add(resolved)
            selected.append((path, kind, relative))

    ledger = Path(settings.ledger_path or data_root / "ledger.jsonl").resolve()
    if ledger.is_file() and not _under(ledger, data_root) and ledger not in seen:
        selected.append((ledger, "ledger", ledger.name))
        seen.add(ledger)
    return selected


def _default_destination(settings: Settings) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path.cwd() / "backups" / f"erasureproof-{stamp}.zip"


def create_backup(
    destination: str | Path | None = None,
    *,
    settings: Settings | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    settings = settings or get_settings()
    destination = Path(destination) if destination is not None else _default_destination(settings)
    if destination.exists() and destination.is_dir():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        destination = destination / f"erasureproof-{stamp}.zip"
    destination = destination.expanduser().resolve()

    roots = [
        Path(settings.data_dir).resolve(),
        Path(settings.evidence_dir or settings.data_dir / "evidence").resolve(),
        Path(settings.attestation_dir or settings.data_dir / "attestations").resolve(),
    ]
    if any(_under(destination, root) for root in roots):
        raise BackupError("backup destination must be outside the live data directories")
    if destination.exists() and not overwrite:
        raise BackupError(f"backup already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)

    database = _database_path(settings)
    files: list[BackupFile] = []
    warnings: list[str] = []
    with tempfile.TemporaryDirectory(prefix="erasureproof-backup-") as workspace:
        db_snapshot: Path | None = None
        if database is not None and database.is_file():
            db_snapshot = Path(workspace) / database.name
            _sqlite_snapshot(database, db_snapshot)
            files.append(
                BackupFile(
                    arcname=f"database/{database.name}",
                    kind="database",
                    path=database.name,
                    size=db_snapshot.stat().st_size,
                    sha256=_sha256_file(db_snapshot),
                )
            )
        elif database is not None:
            warnings.append("SQLite database is missing and was not included")
        else:
            warnings.append("PostgreSQL is configured; back it up with pg_dump separately")

        for path, kind, relative in _source_files(settings, database, destination):
            files.append(
                BackupFile(
                    arcname=f"{kind}/{relative}",
                    kind=kind,
                    path=relative,
                    size=path.stat().st_size,
                    sha256=_sha256_file(path),
                )
            )

        manifest_body = {
            "format": FORMAT,
            "format_version": FORMAT_VERSION,
            "app_version": __version__,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "database": {
                "included": db_snapshot is not None,
                "engine": "sqlite" if settings.is_sqlite else "external",
            },
            "files": [item.to_dict() for item in files],
            "warnings": warnings,
        }
        manifest = {
            **manifest_body,
            "signature": {
                "algorithm": "HMAC-SHA256",
                "value": sign_payload(manifest_body, settings.attestation_key),
            },
        }

        temporary = Path(workspace) / "backup.zip"
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for item in files:
                if item.kind == "database":
                    assert db_snapshot is not None
                    archive.write(db_snapshot, item.arcname)
                else:
                    root = _kind_root(item.kind, settings)
                    archive.write(root / item.path, item.arcname)
            archive.writestr(MANIFEST, json.dumps(manifest, indent=2, sort_keys=True) + "\n")

        os.replace(temporary, destination)
        try:
            destination.chmod(0o600)
        except OSError:
            pass
        with destination.open("rb") as handle:
            os.fsync(handle.fileno())

    return {
        "backup": str(destination),
        "bytes": destination.stat().st_size,
        "files": len(files),
        "database_included": database is not None
        and any(item.kind == "database" for item in files),
        "warnings": warnings,
        "manifest": manifest,
    }


def verify_backup(path: str | Path, *, settings: Settings | None = None) -> BackupVerification:
    settings = settings or get_settings()
    path = Path(path).expanduser().resolve()
    errors: list[str] = []
    manifest: dict[str, Any] | None = None
    if not path.is_file():
        return BackupVerification(False, ["backup does not exist"], None, path)
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                errors.append("archive contains duplicate member names")
            if MANIFEST not in names:
                errors.append("manifest.json is missing")
                return BackupVerification(False, errors, None, path)
            info = archive.getinfo(MANIFEST)
            if info.file_size > MAX_MANIFEST_BYTES:
                errors.append("manifest.json is too large")
                return BackupVerification(False, errors, None, path)
            try:
                with archive.open(MANIFEST) as handle:
                    raw = handle.read(MAX_MANIFEST_BYTES + 1)
                manifest = json.loads(raw)
            except (json.JSONDecodeError, UnicodeDecodeError):
                errors.append("manifest.json is not valid JSON")
                return BackupVerification(False, errors, None, path)
            if len(raw) > MAX_MANIFEST_BYTES:
                errors.append("manifest.json is too large")
                return BackupVerification(False, errors, None, path)
            if not isinstance(manifest, dict):
                errors.append("manifest.json must be an object")
                return BackupVerification(False, errors, None, path)
            if manifest.get("format") != FORMAT:
                errors.append("unrecognized backup format")
            if manifest.get("format_version") != FORMAT_VERSION:
                errors.append("unsupported backup format version")
            signature = manifest.get("signature")
            body = {key: value for key, value in manifest.items() if key != "signature"}
            signature_valid = True
            if not isinstance(signature, dict) or not signature.get("value"):
                errors.append("manifest signature is missing")
                signature_valid = False
            elif signature.get("algorithm") != "HMAC-SHA256":
                errors.append("manifest signature algorithm is unsupported")
                signature_valid = False
            elif not verify_signature(body, str(signature["value"]), settings.attestation_key):
                errors.append("manifest signature is invalid")
                signature_valid = False
            if not signature_valid:
                return BackupVerification(False, errors, manifest, path)
            entries = manifest.get("files")
            if not isinstance(entries, list):
                errors.append("manifest files must be a list")
                return BackupVerification(False, errors, manifest, path)

            expected: dict[str, dict[str, Any]] = {}
            for entry in entries:
                if not isinstance(entry, dict):
                    errors.append("manifest contains an invalid file entry")
                    continue
                arcname = str(entry.get("arcname", ""))
                kind = str(entry.get("kind", ""))
                if not _safe_member(arcname):
                    errors.append(f"unsafe archive path: {arcname!r}")
                    continue
                if kind not in KINDS:
                    errors.append(f"invalid file kind: {kind!r}")
                if arcname in expected:
                    errors.append(f"duplicate manifest entry: {arcname}")
                expected[arcname] = entry
                if arcname not in names:
                    errors.append(f"missing archive member: {arcname}")

            extras = set(names) - set(expected) - {MANIFEST}
            for extra in sorted(extras):
                errors.append(f"unexpected archive member: {extra}")
            for arcname, entry in expected.items():
                if arcname not in names:
                    continue
                expected_size = entry.get("size")
                if not isinstance(expected_size, int) or expected_size < 0:
                    errors.append(f"invalid size for {arcname}")
                    continue
                try:
                    with archive.open(arcname) as handle:
                        digest, size = _sha256_stream(handle, expected_size)
                except (OSError, zipfile.BadZipFile) as exc:
                    errors.append(f"cannot read {arcname}: {exc}")
                    continue
                if size != expected_size:
                    errors.append(f"size mismatch for {arcname}")
                if size <= expected_size and digest != entry.get("sha256"):
                    errors.append(f"sha256 mismatch for {arcname}")
    except zipfile.BadZipFile:
        errors.append("backup is not a valid zip archive")
    except OSError as exc:
        errors.append(f"cannot read backup: {exc}")
    return BackupVerification(not errors, errors, manifest, path)


def _kind_root(kind: str, settings: Settings) -> Path:
    if kind == "data":
        return Path(settings.data_dir).resolve()
    if kind == "evidence":
        return Path(settings.evidence_dir or settings.data_dir / "evidence").resolve()
    if kind == "attestations":
        return Path(settings.attestation_dir or settings.data_dir / "attestations").resolve()
    if kind == "ledger":
        return Path(settings.ledger_path or settings.data_dir / "ledger.jsonl").resolve().parent
    raise BackupError(f"unsupported backup kind: {kind}")


def _restore_target(entry: dict[str, Any], settings: Settings) -> Path:
    kind = str(entry.get("kind", ""))
    relative = str(entry.get("path", ""))
    if not _safe_member(relative):
        raise BackupError(f"unsafe restore path: {relative!r}")
    if kind == "database":
        database = _database_path(settings)
        if database is None:
            raise BackupError("backup contains SQLite data but target is not SQLite")
        return database
    if kind == "ledger":
        return Path(settings.ledger_path or settings.data_dir / "ledger.jsonl").resolve()
    root = _kind_root(kind, settings)
    target = (root / relative).resolve()
    if not _under(target, root):
        raise BackupError(f"restore path escapes its root: {relative!r}")
    return target


def _remove_sqlite_sidecars(database: Path) -> None:
    for suffix in ("-wal", "-shm"):
        sidecar = Path(f"{database}{suffix}")
        if sidecar.exists():
            sidecar.unlink()


def restore_backup(
    path: str | Path,
    *,
    settings: Settings | None = None,
    force: bool = False,
) -> dict[str, Any]:
    settings = settings or get_settings()
    verification = verify_backup(path, settings=settings)
    if not verification.valid or verification.manifest is None:
        raise BackupError("backup verification failed: " + "; ".join(verification.errors))

    manifest = verification.manifest
    entry_list = manifest["files"]
    targets = [(entry, _restore_target(entry, settings)) for entry in entry_list]
    existing = [
        str(target) for _, target in targets if target.exists() or Path(f"{target}-wal").exists()
    ]
    if existing and not force:
        preview = ", ".join(existing[:5])
        raise BackupError(f"refusing to overwrite existing files: {preview}")

    restored: list[str] = []
    with zipfile.ZipFile(verification.path) as archive:
        for entry, target in targets:
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                dir=target.parent, prefix=f".{target.name}.restore-", delete=False
            ) as handle:
                temporary = Path(handle.name)
                with archive.open(str(entry["arcname"])) as source:
                    while chunk := source.read(CHUNK):
                        handle.write(chunk)
                handle.flush()
                os.fsync(handle.fileno())
            digest = _sha256_file(temporary)
            if digest != entry["sha256"]:
                temporary.unlink(missing_ok=True)
                raise BackupError(f"restored file failed hash verification: {entry['arcname']}")
            if entry["kind"] == "database":
                _remove_sqlite_sidecars(target)
            os.replace(temporary, target)
            restored.append(str(target))

    record = {
        "restored_at": datetime.now(timezone.utc).isoformat(),
        "backup": verification.path.name,
        "backup_created_at": manifest.get("created_at"),
        "files": len(restored),
    }
    record_path = Path(settings.data_dir).resolve() / "last-restore.json"
    record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return {
        "backup": str(verification.path),
        "files": len(restored),
        "targets": restored,
        "warnings": manifest.get("warnings", []),
    }
