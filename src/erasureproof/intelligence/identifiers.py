"""Identifier discovery and subject matching.

The extractor is deliberately conservative: it favours precision over recall for
ambiguous values such as phone numbers and card numbers. Every value is
normalised before matching so historical formats still line up.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from typing import Any

from ..models.domain import (
    IdentifierType,
    SubjectGraph,
    hash_email,
    normalize_value,
)

_EMAIL_RE = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+", re.IGNORECASE)
_URL_RE = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)
_HANDLE_RE = re.compile(r"(?<![\w@])@[A-Za-z0-9_][A-Za-z0-9_.-]{1,30}", re.ASCII)
_IPV4_RE = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
_PHONE_RE = re.compile(r"(?<![\w])(?:\+|00)?\d(?:[\d\s().-]{6,}\d)(?![\w])")
_HEX_RE = re.compile(r"\b[a-f0-9]{32,64}\b", re.IGNORECASE)
_CARD_RE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
_IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b")

PHONE_MIN_DIGITS = 8
PHONE_MAX_DIGITS = 15


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def _luhn(value: str) -> bool:
    digits = [int(ch) for ch in value if ch.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    checksum = 0
    parity = len(digits) % 2
    for index, digit in enumerate(digits):
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0


def _phone_values(text: str) -> set[str]:
    results: set[str] = set()
    for match in _PHONE_RE.finditer(text):
        raw = match.group(0)
        digits = _digits(raw)
        if not PHONE_MIN_DIGITS <= len(digits) <= PHONE_MAX_DIGITS:
            continue
        has_signal = raw.strip().startswith(("+", "00")) or any(
            ch in raw for ch in " ()-."
        )
        if not has_signal and len(digits) < 10:
            continue
        if len(set(digits)) <= 2:
            continue
        results.add(normalize_value(raw, IdentifierType.PHONE))
    return results


def extract_identifiers(text: str) -> dict[str, list[str]]:
    """Return normalised identifiers grouped by kind."""

    text = text or ""
    emails = {value.lower().rstrip(".,;:") for value in _EMAIL_RE.findall(text)}
    phones = _phone_values(text)
    urls = {value.rstrip(".,;:") for value in _URL_RE.findall(text)}
    handles = {value.lower() for value in _HANDLE_RE.findall(text)}
    ips = {
        value
        for value in _IPV4_RE.findall(text)
        if all(0 <= int(part) <= 255 for part in value.split("."))
    }
    hashes = {value.lower() for value in _HEX_RE.findall(text)}
    cards = {
        _digits(value)
        for value in _CARD_RE.findall(text)
        if _luhn(_digits(value))
    }
    ibans = {value.upper() for value in _IBAN_RE.findall(text)}

    found: dict[str, list[str]] = {}
    for kind, values in (
        ("email", emails),
        ("phone", phones),
        ("url", urls),
        ("username", handles),
        ("ip", ips),
        ("hash", hashes),
        ("card", cards),
        ("iban", ibans),
    ):
        if values:
            found[kind] = sorted(values)
    return found


def _iter_subject_values(subject: SubjectGraph) -> Iterable[tuple[str, str]]:
    for identifier in subject.identifiers:
        value = identifier.normalized()
        if not value:
            continue
        if identifier.type is IdentifierType.EMAIL:
            yield "email", value
        elif identifier.type is IdentifierType.PHONE:
            yield "phone", value
        elif identifier.type is IdentifierType.EMAIL_HASH:
            yield "hash", value
        else:
            yield "external_id", value


def _phone_match(found: set[str], wanted: str) -> bool:
    wanted_digits = _digits(wanted)
    if len(wanted_digits) < 7:
        return False
    return any(
        _digits(candidate)[-len(wanted_digits) :] == wanted_digits
        or wanted_digits[-len(_digits(candidate)) :] == _digits(candidate)
        for candidate in found
        if _digits(candidate)
    )


def match_subject(
    found: dict[str, list[str]],
    subject: SubjectGraph,
    names: Iterable[str] = (),
    text: str = "",
) -> dict[str, list[str]]:
    """Return raw values that connect the content to the subject."""

    matched: dict[str, set[str]] = {}
    emails = set(found.get("email", []))
    phones = set(found.get("phone", []))
    hashes = set(found.get("hash", []))
    all_values = {value for values in found.values() for value in values}

    for kind, wanted in _iter_subject_values(subject):
        if kind == "email":
            if wanted in emails:
                matched.setdefault("email", set()).add(wanted)
            if hash_email(wanted) in hashes:
                matched.setdefault("email_hash", set()).add(wanted)
        elif kind == "phone":
            if _phone_match(phones, wanted):
                matched.setdefault("phone", set()).add(wanted)
        elif kind == "hash":
            if wanted in hashes:
                matched.setdefault("hash", set()).add(wanted)
        elif wanted in all_values:
            matched.setdefault(kind, set()).add(wanted)

    haystack = (text or "").lower()
    stable_reference = subject.user_id.strip()
    if len(stable_reference) >= 4 and re.search(
        rf"(?<!\w){re.escape(stable_reference.lower())}(?!\w)", haystack
    ):
        matched.setdefault("stable_reference", set()).add(stable_reference)
    for name in names:
        cleaned = name.strip()
        if len(cleaned) < 3:
            continue
        pattern = re.compile(rf"(?<!\w){re.escape(cleaned.lower())}(?!\w)")
        if pattern.search(haystack):
            matched.setdefault("name", set()).add(cleaned)

    return {kind: sorted(values) for kind, values in sorted(matched.items())}


def mask_identifier(value: str, kind: str = "") -> str:
    value = str(value)
    if kind in {"email", "email_hash"} or "@" in value:
        if "@" in value:
            local, _, domain = value.partition("@")
            return f"{local[:1]}***@{domain}"
        return value[:4] + "***" + value[-4:] if len(value) > 8 else "***"
    digits = _digits(value)
    if len(digits) >= 7:
        return f"{digits[:3]}***{digits[-2:]}"
    if len(value) <= 4:
        return "***"
    return f"{value[:2]}***{value[-2:]}"


def mask_value(value: str) -> str:
    return mask_identifier(value)


def mask_mapping(values: dict[str, list[str]]) -> dict[str, list[str]]:
    return {
        kind: sorted({mask_identifier(value, kind) for value in items})
        for kind, items in sorted(values.items())
    }


def short_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def snippets(text: str, values: Iterable[str], limit: int = 3, width: int = 90) -> list[str]:
    """Return short, masked context windows around matching values."""

    if not text:
        return []
    lowered = text.lower()
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        needle = str(value).lower()
        if not needle:
            continue
        start = 0
        while len(result) < limit:
            index = lowered.find(needle, start)
            if index < 0:
                break
            left = max(0, index - width // 2)
            right = min(len(text), index + len(needle) + width // 2)
            window = " ".join(text[left:right].split())
            for candidate in values:
                if len(str(candidate)) >= 3:
                    window = re.sub(
                        re.escape(str(candidate)),
                        mask_identifier(str(candidate)),
                        window,
                        flags=re.IGNORECASE,
                    )
            if window and window not in seen:
                seen.add(window)
                result.append(window)
            start = index + len(needle)
    return result


def metadata_text(metadata: dict[str, Any]) -> str:
    parts: list[str] = []
    for key, value in metadata.items():
        if isinstance(value, (str, int, float)):
            parts.append(f"{key}={value}")
        elif isinstance(value, list):
            parts.append(f"{key}=" + " ".join(str(item) for item in value))
        elif isinstance(value, dict):
            parts.append(f"{key}=" + " ".join(f"{k}:{v}" for k, v in value.items()))
    return "\n".join(parts)
