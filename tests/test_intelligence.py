from __future__ import annotations

import io
import json
import shutil
import tarfile
import zipfile
from datetime import datetime, timedelta, timezone

from erasureproof.connectors.filesystem import FilesystemConnector
from erasureproof.evidence.store import EvidenceStore
from erasureproof.intelligence.extract import ExtractionLimits, extract_bytes
from erasureproof.intelligence.identifiers import extract_identifiers, match_subject
from erasureproof.intelligence.scanner import scan_directory
from erasureproof.models.domain import (
    Action,
    Identifier,
    IdentifierType,
    State,
    SubjectGraph,
)

NOW = datetime.now(timezone.utc)
AUDIT_AT = NOW + timedelta(hours=1)


def _subject() -> SubjectGraph:
    return SubjectGraph(
        user_id="u_1",
        identifiers=[Identifier(IdentifierType.EMAIL, "alice@example.com")],
    )


def test_extract_text_json_and_zip() -> None:
    text = extract_bytes(b"owner alice@example.com phone +1 555 0100", "note.txt")
    assert "alice@example.com" in extract_identifiers(text.text)["email"]

    payload = json.dumps({"email": "alice@example.com"}).encode()
    assert "alice@example.com" in extract_bytes(payload, "record.json").text

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("nested/contact.txt", "email=alice@example.com")
    extracted = extract_bytes(buffer.getvalue(), "bundle.zip")
    assert "alice@example.com" in extracted.text
    assert any("nested/contact.txt" in child for child in extracted.children)

    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w:gz") as archive:
        body = b"email=alice@example.com"
        info = tarfile.TarInfo("exports/contact.txt")
        info.size = len(body)
        archive.addfile(info, io.BytesIO(body))
    tar_extracted = extract_bytes(tar_buffer.getvalue(), "bundle.tar.gz")
    assert "alice@example.com" in tar_extracted.text


def test_extract_pdf_text() -> None:
    pytest = __import__("pytest")
    reportlab = pytest.importorskip("reportlab.pdfgen.canvas")
    buffer = io.BytesIO()
    canvas = reportlab.Canvas(buffer)
    canvas.drawString(72, 720, "Customer alice@example.com")
    canvas.save()
    extracted = extract_bytes(buffer.getvalue(), "invoice.pdf")
    assert "alice@example.com" in extracted.text
    assert extracted.warnings == [] or "alice@example.com" in extracted.text


def test_image_ocr_when_tools_are_available(tmp_path) -> None:
    pytest = __import__("pytest")
    if not shutil.which("tesseract"):
        pytest.skip("tesseract is not installed")
    image_module = pytest.importorskip("PIL.Image")
    draw_module = pytest.importorskip("PIL.ImageDraw")
    font_module = pytest.importorskip("PIL.ImageFont")

    image = image_module.new("RGB", (1000, 240), "white")
    draw = draw_module.Draw(image)
    try:
        font = font_module.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 48
        )
    except OSError:
        font = font_module.load_default()
    draw.text((30, 80), "alice@example.com", fill="black", font=font)
    path = tmp_path / "scan.png"
    image.save(path)

    extracted = extract_bytes(path.read_bytes(), path.name, ExtractionLimits(ocr=True))
    assert extracted.ocr_used
    assert "alice@example.com" in extracted.text.lower()


def test_match_subject_uses_historical_identifier() -> None:
    found = extract_identifiers("old contact alice.old@example.com")
    subject = SubjectGraph(
        user_id="u_1",
        identifiers=[
            Identifier(IdentifierType.EMAIL, "alice@example.com"),
            Identifier(IdentifierType.EMAIL, "alice.old@example.com"),
        ],
    )
    matched = match_subject(found, subject)
    assert "email" in matched
    assert "alice.old@example.com" in matched["email"]


def test_scanner_finds_subject_and_records_evidence(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    exported = workspace / "exports"
    exported.mkdir(parents=True)
    (exported / "alice.txt").write_text("email=alice@example.com", encoding="utf-8")
    (exported / "bob.txt").write_text("email=bob@example.com", encoding="utf-8")
    store = EvidenceStore(tmp_path / "evidence")

    report = scan_directory(
        workspace,
        subject=_subject(),
        store=store,
        limits=ExtractionLimits(ocr=False),
        max_files=50,
    )

    assert report.scanned == 2
    assert [item.name for item in report.matched_files] == ["alice.txt"]
    assert report.matched_files[0].evidence_id.startswith("ev_")
    assert report.severity in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


def test_stable_user_reference_is_matched_but_not_redacted(tmp_path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    target = root / "account.txt"
    target.write_text(
        "user_id=u_1001 email=alice@example.com", encoding="utf-8"
    )
    connector = FilesystemConnector(
        "con_fs",
        "account_db",
        {"root": str(root), "default_category": "PRIMARY_ACCOUNT"},
    )
    subject = SubjectGraph(
        user_id="u_1001",
        identifiers=[Identifier(IdentifierType.EMAIL, "alice@example.com")],
    )

    resource = connector.discover(subject, AUDIT_AT)[0]
    assert "u_1001" not in resource.payload["subject_values"]
    assert resource.payload["stable_reference"] == "u_1001"
    assert connector.remediate(resource, Action.REDACT).success
    text = target.read_text(encoding="utf-8")
    assert "alice@example.com" not in text
    assert "u_1001" in text


def test_filesystem_connector_redacts_and_verifies(tmp_path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    target = root / "export.csv"
    target.write_text("name,email\nAlice,alice@example.com\n", encoding="utf-8")
    store = EvidenceStore(tmp_path / "evidence")
    connector = FilesystemConnector(
        "con_fs",
        "support_exports",
        {"root": str(root), "categories": {"*.csv": "EXPORT"}},
        evidence_store=store,
    )

    resources = connector.discover(_subject(), AUDIT_AT)
    assert len(resources) == 1
    resource = resources[0]
    assert resource.evidence_id.startswith("ev_")
    assert connector.remediate(resource, Action.REDACT).success
    assert connector.verify(resource, State.REDACTED).passed
    assert "alice@example.com" not in target.read_text(encoding="utf-8")
    assert connector.remediate(resource, Action.DELETE).success
    assert connector.verify(resource, State.ABSENT).passed
