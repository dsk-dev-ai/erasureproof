"""Bounded workspace scanning.

The scanner walks a directory (or a single file), extracts text through the
intelligence pipeline, matches the subject graph, and records content-addressed
evidence. It never follows symlinks and never writes into the scanned tree.
"""

from __future__ import annotations

import os
from collections import Counter
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..models.domain import SubjectGraph
from .extract import ExtractionLimits, available_tools, extract_bytes
from .identifiers import extract_identifiers, match_subject, metadata_text, snippets
from .models import ScannedFile, ScanReport

SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".erasureproof",
    ".cache",
}


def _risk(matched_files: list[ScannedFile]) -> tuple[int, str]:
    if not matched_files:
        return 0, "NONE"
    score = 0
    for item in matched_files:
        score += 8 + min(24, 4 * item.matched_count)
        if item.ocr_used:
            score += 6
        if item.mime.startswith("image/") or item.mime == "application/pdf":
            score += 4
    score = min(100, score)
    if score >= 75:
        return score, "CRITICAL"
    if score >= 50:
        return score, "HIGH"
    if score >= 25:
        return score, "MEDIUM"
    return score, "LOW"


def _recommendations(files: list[ScannedFile]) -> list[str]:
    if not files:
        return [
            "No subject identifiers were found in this scope.",
            "Add database, object-store and exposure collectors to widen coverage.",
        ]
    recommendations = [
        "Apply the deletion policy to every matched file; prefer delete for binary media.",
        "Redact text-based exports and re-run this scan to prove the identifiers are gone.",
    ]
    if any(item.ocr_used for item in files):
        recommendations.append("Review OCR-matched images; remove or redact the source image.")
    if any(
        "archive" in item.metadata.get("mime", "") or item.metadata.get("entries")
        for item in files
    ):
        recommendations.append("Purge matching archive members and rebuild archives without them.")
    if any(item.mime == "application/pdf" for item in files):
        recommendations.append(
            "Delete or flatten PDFs that contain identifiers in text or OCR layers."
        )
    return recommendations


def scan_file(
    path: str | Path,
    subject: SubjectGraph | None = None,
    names: Iterable[str] = (),
    store: Any | None = None,
    limits: ExtractionLimits | None = None,
    include_all: bool = False,
) -> ScannedFile | None:
    limits = limits or ExtractionLimits()
    path = Path(path)
    try:
        stat = path.stat()
        with path.open("rb") as handle:
            raw = handle.read(limits.max_bytes)
    except OSError:
        return None
    document = extract_bytes(raw, path.name, limits=limits)
    if stat.st_size > limits.max_bytes:
        document.warnings.append(
            f"file truncated at {limits.max_bytes} bytes for scanning"
        )
    combined = document.text
    if document.metadata:
        combined = f"{combined}\n{metadata_text(document.metadata)}"
    identifiers = extract_identifiers(combined)
    matched = match_subject(identifiers, subject, names, combined) if subject else {}
    if subject and not matched and not include_all:
        return None
    if not subject and not include_all and not identifiers:
        return None

    all_values = [value for values in identifiers.values() for value in values]
    matched_values = [value for values in matched.values() for value in values]
    evidence_id = ""
    if store is not None:
        mime = str(document.metadata.get("mime", "application/octet-stream"))
        evidence_id = store.put(
            raw,
            source=f"filesystem:{path}",
            captured_at=datetime.now(timezone.utc),
            content_type=mime,
        ).evidence_id

    return ScannedFile(
        path=str(path),
        name=path.name,
        sha256=str(document.metadata.get("sha256", "")),
        size=len(raw),
        mime=str(document.metadata.get("mime", "application/octet-stream")),
        modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
        identifiers=identifiers,
        matched=matched,
        snippets=snippets(combined, matched_values or all_values),
        metadata=document.to_dict().get("metadata", {}),
        evidence_id=evidence_id,
        ocr_used=document.ocr_used,
        warnings=document.warnings,
    )


def scan_directory(
    root: str | Path,
    subject: SubjectGraph | None = None,
    names: Iterable[str] = (),
    store: Any | None = None,
    limits: ExtractionLimits | None = None,
    include_all: bool = False,
    include_hidden: bool = False,
    max_files: int = 5000,
    as_of: datetime | None = None,
) -> ScanReport:
    started = datetime.now(timezone.utc)
    limits = limits or ExtractionLimits()
    root = Path(root).expanduser()
    matched_files: list[ScannedFile] = []
    errors: list[str] = []
    identifiers: dict[str, set[str]] = {}
    scanned = 0

    if not root.exists():
        return ScanReport(
            root=str(root),
            started_at=started,
            completed_at=datetime.now(timezone.utc),
            errors=[f"path does not exist: {root}"],
            tools=available_tools(),
        )

    candidates: list[Path] = []
    if root.is_file():
        candidates = [root]
    else:
        for current, dirnames, filenames in os.walk(root):
            current_path = Path(current)
            dirnames[:] = sorted(
                name
                for name in dirnames
                if (include_hidden or not name.startswith(".")) and name not in SKIP_DIRS
            )
            for filename in sorted(filenames):
                if filename.startswith(".") and not include_hidden:
                    continue
                candidate = current_path / filename
                if candidate.is_symlink():
                    continue
                candidates.append(candidate)
                if len(candidates) >= max_files:
                    errors.append(f"file limit reached ({max_files})")
                    break
            if len(candidates) >= max_files:
                break

    for candidate in candidates:
        if candidate.is_symlink():
            continue
        if as_of is not None:
            try:
                modified = datetime.fromtimestamp(candidate.stat().st_mtime, tz=timezone.utc)
            except OSError:
                continue
            if modified > as_of:
                continue
        item = scan_file(
            candidate,
            subject=subject,
            names=names,
            store=store,
            limits=limits,
            include_all=include_all,
        )
        scanned += 1
        if item is None:
            continue
        matched_files.append(item)
        for kind, values in item.identifiers.items():
            identifiers.setdefault(kind, set()).update(values)

    matched_files.sort(key=lambda item: (-item.matched_count, item.path))
    score, severity = _risk(matched_files)
    if errors:
        severity = severity

    report = ScanReport(
        root=str(root),
        started_at=started,
        completed_at=datetime.now(timezone.utc),
        scanned=scanned,
        matched_files=matched_files,
        identifiers={
            kind: sorted(values) for kind, values in sorted(identifiers.items())
        },
        errors=errors,
        tools=available_tools(),
        risk_score=score,
        severity=severity,
        recommendations=_recommendations(matched_files),
    )
    return report


def summarise_kinds(files: list[ScannedFile]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for item in files:
        counter.update(item.identifiers.keys())
    return dict(sorted(counter.items()))
