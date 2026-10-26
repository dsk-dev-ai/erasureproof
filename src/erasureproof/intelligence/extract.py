"""Content extraction for local evidence.

Supported inputs:

* plain text, logs, JSON, CSV, XML and HTML;
* PDFs (text layer first, OCR fallback through Poppler + Tesseract);
* images (OCR + EXIF, when Tesseract/Pillow are available);
* Office Open XML documents (docx, xlsx, pptx);
* zip, tar and gzip archives (bounded, no extraction to disk);
* SQLite databases;
* arbitrary binaries via a printable-string fallback.

Everything runs locally. Nothing in this module makes a network request.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import mimetypes
import re
import shutil
import sqlite3
import subprocess
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from .models import ExtractedDocument

_TEXT_MIMES = {
    "application/javascript",
    "application/json",
    "application/ld+json",
    "application/sql",
    "application/x-httpd-php",
    "application/x-sh",
    "application/x-yaml",
    "application/xml",
    "image/svg+xml",
}
_TEXT_EXTENSIONS = {
    ".txt",
    ".log",
    ".md",
    ".rst",
    ".json",
    ".jsonl",
    ".ndjson",
    ".csv",
    ".tsv",
    ".xml",
    ".html",
    ".htm",
    ".yaml",
    ".yml",
    ".ini",
    ".cfg",
    ".conf",
    ".env",
    ".sql",
    ".py",
    ".js",
    ".ts",
    ".sh",
    ".java",
    ".go",
    ".rb",
    ".php",
    ".eml",
}
_OFFICE_EXTENSIONS = {".docx", ".xlsx", ".pptx", ".odt", ".ods", ".odp"}
_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp", ".gif"}
_PDF_EXTENSIONS = {".pdf"}
_SQLITE_EXTENSIONS = {".db", ".sqlite", ".sqlite3"}
_SQLITE_MAGIC = b"SQLite format 3\x00"
_STRING_RE = re.compile(rb"[ -~]{6,}")


def _jsonable(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, bytes):
        return value[:64].hex()
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    try:
        return str(value)
    except Exception:
        return repr(value)


@dataclass(slots=True)
class ExtractionLimits:
    max_bytes: int = 8_000_000
    max_text: int = 4_000_000
    max_pages: int = 20
    max_archive_entries: int = 200
    max_archive_bytes: int = 60_000_000
    max_depth: int = 2
    ocr: bool = True
    strings: bool = True


def tool_path(name: str) -> str | None:
    return shutil.which(name)


def available_tools() -> dict[str, str]:
    names = (
        "tesseract",
        "pdftotext",
        "pdftoppm",
        "pdfimages",
        "exiftool",
        "7z",
        "binwalk",
        "strings",
        "sqlite3",
    )
    return {name: tool_path(name) or "" for name in names}


def _run(args: list[str], timeout: int = 60) -> str:
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if completed.returncode != 0:
        return ""
    return completed.stdout.decode("utf-8", errors="ignore")


def _decode(raw: bytes) -> str:
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def _looks_text(raw: bytes) -> bool:
    if not raw:
        return True
    if b"\x00" in raw[:4096]:
        return False
    sample = raw[:4096]
    printable = sum(
        1
        for byte in sample
        if byte in b"\n\r\t" or 32 <= byte <= 126 or byte >= 128
    )
    return printable / len(sample) > 0.85


def detect_mime(filename: str, raw: bytes) -> str:
    lowered = filename.lower()
    suffix = Path(lowered).suffix
    if raw.startswith(b"%PDF"):
        return "application/pdf"
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if raw.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if raw.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if raw.startswith(b"BM"):
        return "image/bmp"
    if raw.startswith(b"RIFF") and raw[8:12] == b"WEBP":
        return "image/webp"
    if raw.startswith(_SQLITE_MAGIC):
        return "application/vnd.sqlite3"
    if raw.startswith(b"PK\x03\x04"):
        if suffix in _OFFICE_EXTENSIONS:
            return "application/vnd.openxmlformats-officedocument"
        return "application/zip"
    if raw.startswith(b"\x1f\x8b"):
        return "application/gzip"
    if suffix in _PDF_EXTENSIONS:
        return "application/pdf"
    if suffix in _SQLITE_EXTENSIONS:
        return "application/vnd.sqlite3"
    guessed, _ = mimetypes.guess_type(lowered)
    if guessed:
        return guessed
    if suffix in _TEXT_EXTENSIONS or _looks_text(raw):
        return "text/plain"
    return "application/octet-stream"


class _TextHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.title = ""
        self._in_title = False
        self._skip = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip += 1
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip:
            self._skip -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        text = data.strip()
        if not text:
            return
        if self._in_title:
            self.title += text
        self.parts.append(text)


def _html_to_text(raw: str) -> tuple[str, str]:
    parser = _TextHTMLParser()
    try:
        parser.feed(raw)
    except Exception:
        return raw, ""
    return "\n".join(parser.parts), parser.title


def _flatten_json(value: Any, prefix: str = "", depth: int = 0) -> list[str]:
    if depth > 8:
        return []
    if isinstance(value, dict):
        lines: list[str] = []
        for key, item in value.items():
            lines.extend(_flatten_json(item, f"{prefix}.{key}" if prefix else str(key), depth + 1))
        return lines
    if isinstance(value, list):
        lines = []
        for index, item in enumerate(value[:500]):
            lines.extend(_flatten_json(item, f"{prefix}[{index}]", depth + 1))
        return lines
    return [f"{prefix}: {value}"]


def _extract_structured(text: str, mime: str) -> str:
    lowered = mime.lower()
    if "html" in lowered or "xml" in lowered:
        cleaned, _ = _html_to_text(text)
        return cleaned or text
    if "json" in lowered:
        try:
            return "\n".join(_flatten_json(json.loads(text)))
        except (json.JSONDecodeError, TypeError):
            return text
    if mime in {"text/csv", "text/tab-separated-values"}:
        try:
            rows = list(csv.reader(io.StringIO(text)))[:500]
            return "\n".join("\t".join(row) for row in rows)
        except csv.Error:
            return text
    return text


def _ocr_image(path: Path, timeout: int = 90) -> tuple[str, list[str]]:
    tesseract = tool_path("tesseract")
    if not tesseract:
        return "", ["OCR unavailable: install tesseract"]
    text = _run([tesseract, str(path), "stdout", "-l", "eng", "--psm", "3"], timeout)
    return text, [] if text else ["OCR returned no text"]


def _image_metadata(path: Path) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    try:
        from PIL import Image  # type: ignore

        with Image.open(path) as image:
            metadata.update(
                {
                    "format": image.format,
                    "mode": image.mode,
                    "width": image.width,
                    "height": image.height,
                }
            )
            exif = image.getexif()
            if exif:
                metadata["exif"] = {
                    str(key): _jsonable(value)
                    for key, value in exif.items()
                    if key != 34853  # GPS IFD: never copy location metadata
                }
            info = {
                key: _jsonable(value)
                for key, value in (image.info or {}).items()
                if key not in {"icc_profile"}
            }
            if info:
                metadata["image_info"] = info
    except Exception as exc:
        metadata["image_error"] = str(exc)
    return metadata


def _extract_pdf(raw: bytes, limits: ExtractionLimits) -> ExtractedDocument:
    text_parts: list[str] = []
    pages = 0
    warnings: list[str] = []
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(io.BytesIO(raw))
        pages = len(reader.pages)
        for page in reader.pages[: limits.max_pages]:
            try:
                text_parts.append(page.extract_text() or "")
            except Exception as exc:
                warnings.append(f"pdf page extraction failed: {exc}")
    except Exception as exc:
        warnings.append(f"pdf text layer unavailable: {exc}")

    text = "\n".join(text_parts).strip()
    ocr_used = False
    if len(text) < 40:
        ocr_text, ocr_warnings = _pdf_ocr(raw, limits)
        warnings.extend(ocr_warnings)
        if ocr_text.strip():
            text = ocr_text
            ocr_used = True

    if not text:
        text = _strings(raw)
    return ExtractedDocument(
        text=_clip(text, limits.max_text),
        metadata={"pages": pages},
        pages=pages,
        ocr_used=ocr_used,
        warnings=warnings,
    )


def _pdf_ocr(raw: bytes, limits: ExtractionLimits) -> tuple[str, list[str]]:
    pdftoppm = tool_path("pdftoppm")
    tesseract = tool_path("tesseract")
    if not pdftoppm or not tesseract:
        return "", ["PDF OCR unavailable: install poppler-utils and tesseract"]
    with tempfile.TemporaryDirectory(prefix="erasureproof-pdf-") as directory:
        source = Path(directory) / "source.pdf"
        source.write_bytes(raw)
        prefix = Path(directory) / "page"
        _run(
            [
                pdftoppm,
                "-r",
                "180",
                "-png",
                "-f",
                "1",
                "-l",
                str(limits.max_pages),
                str(source),
                str(prefix),
            ],
            timeout=120,
        )
        pages = sorted(Path(directory).glob("page*.png"))
        if not pages:
            return "", ["PDF OCR produced no page images"]
        texts: list[str] = []
        warnings: list[str] = []
        for page in pages[: limits.max_pages]:
            text = _run([tesseract, str(page), "stdout", "-l", "eng", "--psm", "3"], 120)
            if text.strip():
                texts.append(text)
            else:
                warnings.append(f"OCR produced no text for {page.name}")
        return "\n\n".join(texts), warnings


def _strings(raw: bytes, limit: int = 400_000) -> str:
    matches = _STRING_RE.findall(raw[: limit * 4])
    return "\n".join(match.decode("utf-8", errors="ignore") for match in matches)[:limit]


def _extract_image(raw: bytes, filename: str, limits: ExtractionLimits) -> ExtractedDocument:
    with tempfile.TemporaryDirectory(prefix="erasureproof-image-") as directory:
        path = Path(directory) / Path(filename).name
        path.write_bytes(raw)
        metadata = _image_metadata(path)
        text = ""
        warnings: list[str] = []
        ocr_used = False
        if limits.ocr:
            text, warnings = _ocr_image(path)
            ocr_used = bool(text)
        if not text:
            text = _strings(raw)
        return ExtractedDocument(
            text=_clip(text, limits.max_text),
            metadata=metadata,
            ocr_used=ocr_used,
            warnings=warnings,
        )


def _xml_text(raw: bytes) -> str:
    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError:
        return _decode(raw)
    return "\n".join(part.strip() for part in root.itertext() if part.strip())


def _extract_office(raw: bytes, limits: ExtractionLimits) -> ExtractedDocument:
    texts: list[str] = []
    children: list[str] = []
    warnings: list[str] = []
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            for info in archive.infolist()[: limits.max_archive_entries]:
                if info.is_dir():
                    continue
                children.append(info.filename)
                lowered = info.filename.lower()
                if not lowered.endswith((".xml", ".rels")):
                    continue
                if info.file_size > limits.max_archive_bytes // 4:
                    continue
                try:
                    body = archive.read(info)[: limits.max_text]
                except (RuntimeError, zipfile.BadZipFile) as exc:
                    warnings.append(f"{info.filename}: {exc}")
                    continue
                text = _xml_text(body)
                if text:
                    texts.append(f"[{info.filename}]\n{text}")
    except zipfile.BadZipFile as exc:
        warnings.append(f"invalid office document: {exc}")
    return ExtractedDocument(
        text=_clip("\n".join(texts), limits.max_text),
        metadata={"entries": children[: limits.max_archive_entries]},
        children=children,
        warnings=warnings,
    )


def _extract_sqlite(raw: bytes, limits: ExtractionLimits) -> ExtractedDocument:
    with tempfile.TemporaryDirectory(prefix="erasureproof-sqlite-") as directory:
        path = Path(directory) / "snapshot.db"
        path.write_bytes(raw)
        lines: list[str] = []
        tables: list[str] = []
        try:
            connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            try:
                cursor = connection.cursor()
                names = [
                    row[0]
                    for row in cursor.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                    ).fetchall()
                ]
                for name in names:
                    tables.append(str(name))
                    lines.append(f"[table {name}]")
                    try:
                        rows = cursor.execute(
                            f'SELECT * FROM "{str(name).replace(chr(34), chr(34) * 2)}" LIMIT 25'
                        ).fetchall()
                    except sqlite3.Error as exc:
                        lines.append(f"error: {exc}")
                        continue
                    for row in rows:
                        lines.append("\t".join(str(value) for value in row if value is not None))
                    if len(lines) > 5000:
                        break
            finally:
                connection.close()
        except sqlite3.Error as exc:
            return ExtractedDocument(warnings=[f"sqlite read failed: {exc}"])
    return ExtractedDocument(
        text=_clip("\n".join(lines), limits.max_text),
        metadata={"tables": tables},
    )


def _extract_archive(
    raw: bytes, filename: str, limits: ExtractionLimits, depth: int
) -> ExtractedDocument:
    lowered = filename.lower()
    if lowered.endswith((".tar", ".tgz", ".tar.gz")):
        members = _tar_members(raw, limits)
    else:
        members = _zip_members(raw, limits)
    texts: list[str] = []
    children: list[str] = []
    warnings: list[str] = []
    total = 0
    for name, body in members:
        children.append(name)
        if len(children) > limits.max_archive_entries:
            warnings.append("archive entry limit reached")
            break
        total += len(body)
        if total > limits.max_archive_bytes:
            warnings.append("archive uncompressed size limit reached")
            break
        suffix = Path(name).suffix.lower()
        if depth >= limits.max_depth:
            continue
        if suffix in _TEXT_EXTENSIONS or suffix in _OFFICE_EXTENSIONS:
            nested = extract_bytes(
                body[: limits.max_bytes],
                name,
                limits=limits,
                depth=depth + 1,
            )
            if nested.text:
                texts.append(f"[{name}]\n{nested.text}")
            warnings.extend(nested.warnings)
        elif (
            suffix in _PDF_EXTENSIONS
            or suffix in _IMAGE_EXTENSIONS
            or name.lower().endswith((".tar", ".tgz", ".tar.gz", ".zip"))
        ):
            nested = extract_bytes(
                body[: limits.max_bytes],
                name,
                limits=limits,
                depth=depth + 1,
            )
            if nested.text:
                texts.append(f"[{name}]\n{nested.text}")
            warnings.extend(nested.warnings)
    return ExtractedDocument(
        text=_clip("\n\n".join(texts), limits.max_text),
        metadata={"entries": children},
        children=children,
        warnings=warnings,
    )


def _zip_members(raw: bytes, limits: ExtractionLimits) -> list[tuple[str, bytes]]:
    members: list[tuple[str, bytes]] = []
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            for info in archive.infolist()[: limits.max_archive_entries]:
                if info.is_dir() or info.flag_bits & 0x1:
                    continue
                if info.file_size > limits.max_bytes:
                    continue
                if info.compress_size and info.file_size / max(info.compress_size, 1) > 200:
                    continue
                try:
                    members.append((info.filename, archive.read(info)))
                except (RuntimeError, zipfile.BadZipFile, NotImplementedError):
                    continue
    except zipfile.BadZipFile:
        return []
    return members


def _tar_members(raw: bytes, limits: ExtractionLimits) -> list[tuple[str, bytes]]:
    members: list[tuple[str, bytes]] = []
    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:*") as archive:
            for info in archive.getmembers()[: limits.max_archive_entries]:
                if not info.isfile() or info.size > limits.max_bytes:
                    continue
                handle = archive.extractfile(info)
                if handle is None:
                    continue
                members.append((info.name, handle.read(limits.max_bytes)))
    except (tarfile.TarError, OSError):
        return []
    return members


def _extract_gzip(raw: bytes, limits: ExtractionLimits, depth: int) -> ExtractedDocument:
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as handle:
            body = handle.read(limits.max_bytes + 1)
    except (OSError, EOFError) as exc:
        return ExtractedDocument(warnings=[f"gzip read failed: {exc}"])
    if len(body) > limits.max_bytes:
        body = body[: limits.max_bytes]
    return extract_bytes(body, "decompressed", limits=limits, depth=depth + 1)


def _clip(text: str, limit: int) -> str:
    return text[:limit] if len(text) > limit else text


def extract_bytes(
    raw: bytes,
    filename: str = "",
    limits: ExtractionLimits | None = None,
    depth: int = 0,
) -> ExtractedDocument:
    limits = limits or ExtractionLimits()
    if depth > limits.max_depth:
        return ExtractedDocument(warnings=["maximum extraction depth reached"])
    if len(raw) > limits.max_bytes:
        raw = raw[: limits.max_bytes]

    mime = detect_mime(filename, raw)
    suffix = Path(filename.lower()).suffix
    metadata: dict[str, Any] = {
        "filename": filename,
        "mime": mime,
        "size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }

    if mime == "application/pdf" or suffix in _PDF_EXTENSIONS:
        document = _extract_pdf(raw, limits)
    elif mime.startswith("image/") or suffix in _IMAGE_EXTENSIONS:
        document = _extract_image(raw, filename, limits)
    elif suffix in _OFFICE_EXTENSIONS:
        document = _extract_office(raw, limits)
    elif mime == "application/vnd.sqlite3" or suffix in _SQLITE_EXTENSIONS:
        document = _extract_sqlite(raw, limits)
    elif mime == "application/zip" or suffix == ".zip":
        document = _extract_archive(raw, filename, limits, depth)
    elif mime == "application/gzip" or suffix == ".gz" or filename.lower().endswith(".tgz"):
        if filename.lower().endswith((".tgz", ".tar.gz")):
            document = _extract_archive(raw, filename, limits, depth)
        else:
            document = _extract_gzip(raw, limits, depth)
    elif mime == "application/x-tar" or suffix == ".tar":
        document = _extract_archive(raw, filename, limits, depth)
    elif mime.startswith("text/") or mime in _TEXT_MIMES or suffix in _TEXT_EXTENSIONS:
        text = _decode(raw)
        document = ExtractedDocument(text=_clip(_extract_structured(text, mime), limits.max_text))
    elif _looks_text(raw):
        document = ExtractedDocument(text=_clip(_decode(raw), limits.max_text))
    else:
        text = _strings(raw) if limits.strings else ""
        document = ExtractedDocument(
            text=_clip(text, limits.max_text),
            warnings=[] if text else ["no extractable text"],
        )

    document.metadata = {**metadata, **(document.metadata or {})}
    return document


def extract_file(path: str | Path, limits: ExtractionLimits | None = None) -> ExtractedDocument:
    limits = limits or ExtractionLimits()
    path = Path(path)
    try:
        with path.open("rb") as handle:
            raw = handle.read(limits.max_bytes)
    except OSError as exc:
        return ExtractedDocument(warnings=[f"read failed: {exc}"])
    return extract_bytes(raw, path.name, limits=limits)
