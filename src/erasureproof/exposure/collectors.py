"""Passive public-source collectors.

Each collector is explicit about its source, records the raw response as
evidence, and never authenticates to, exploits or modifies a third party.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

from ..intelligence.extract import ExtractionLimits, extract_bytes
from ..intelligence.identifiers import (
    extract_identifiers,
    mask_identifier,
    snippets,
)
from ..models.domain import IdentifierType, normalize_value
from .http import FetchError, HttpClient, UnsafeUrlError
from .models import ExposureHit, ExposureTarget

TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _title(raw: bytes, fallback: str = "") -> str:
    try:
        text = raw.decode("utf-8", errors="ignore")
    except Exception:
        return fallback
    match = TITLE_RE.search(text)
    if match:
        return " ".join(match.group(1).split())[:200]
    return fallback


def _match(target: ExposureTarget, haystack: str) -> list[str]:
    found = extract_identifiers(haystack)
    emails = {value.lower() for value in found.get("email", [])}
    phones = {value for value in found.get("phone", [])}
    lowered = haystack.lower()
    matched: list[str] = []
    for email in target.emails():
        if email in emails or email in lowered:
            matched.append(email)
    for phone in target.phones():
        wanted = _digits(phone)
        if any(
            wanted and _digits(candidate)[-len(wanted) :] == wanted
            for candidate in phones
        ):
            matched.append(phone)
    for name in target.names():
        if re.search(rf"(?<!\w){re.escape(name)}(?!\w)", haystack, re.IGNORECASE):
            matched.append(name)
    for username in target.usernames:
        handle = username.lstrip("@")
        if re.search(rf"(?<![\w@])@?{re.escape(handle)}(?![\w])", haystack, re.IGNORECASE):
            matched.append(username)
    return list(dict.fromkeys(matched))


def _snippet(text: str, matched: list[str], title: str = "") -> str:
    context = snippets(text, matched, limit=2, width=160)
    if context:
        return context[0]
    return " ".join((title or text).split())[:240]


def _store(
    store: Any,
    content: Any,
    source: str,
    content_type: str | None = None,
) -> str:
    if store is None:
        return ""
    try:
        return store.put(
            content,
            source=source,
            captured_at=datetime.now(timezone.utc),
            content_type=content_type,
        ).evidence_id
    except Exception:
        return ""


class BaseCollector:
    name = "base"
    kind = "search"
    network = True

    def __init__(self, settings: Any, store: Any, http: HttpClient) -> None:
        self.settings = settings
        self.store = store
        self.http = http
        self.errors: list[str] = []

    def available(self, target: ExposureTarget) -> tuple[bool, str]:
        return True, ""

    def collect(self, target: ExposureTarget) -> list[ExposureHit]:
        raise NotImplementedError

    def _extract_text(self, body: bytes, filename: str) -> str:
        document = extract_bytes(body, filename, limits=ExtractionLimits(max_bytes=len(body)))
        text = document.text
        if not text:
            text = body.decode("utf-8", errors="ignore")
        return text

    def _hit(
        self,
        target: ExposureTarget,
        *,
        url: str,
        kind: str,
        title: str,
        snippet: str,
        matched: list[str],
        confidence: float,
        evidence_id: str,
        first_seen: str | None = None,
        last_seen: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ExposureHit:
        return ExposureHit(
            collector=self.name,
            kind=kind,
            url=url,
            title=title[:300],
            snippet=snippet,
            identifiers=matched,
            confidence=confidence,
            first_seen=first_seen,
            last_seen=last_seen or _now(),
            evidence_id=evidence_id,
            metadata=metadata or {},
        )


class DirectUrlCollector(BaseCollector):
    name = "direct"
    kind = "direct"

    def available(self, target: ExposureTarget) -> tuple[bool, str]:
        return (bool(target.urls), "no URLs supplied")

    def collect(self, target: ExposureTarget) -> list[ExposureHit]:
        hits: list[ExposureHit] = []
        for url in target.urls:
            try:
                response = self.http.get(url)
            except (FetchError, UnsafeUrlError) as exc:
                self.errors.append(f"{url}: {exc}")
                continue
            if response.status >= 400:
                continue
            text = self._extract_text(response.body, url.rsplit("/", 1)[-1] or "page")
            haystack = f"{response.url}\n{text}"
            matched = _match(target, haystack)
            if not matched:
                continue
            evidence_id = _store(
                self.store,
                response.body,
                source=f"exposure:direct:{response.url}",
                content_type=response.content_type or "text/html",
            )
            hits.append(
                self._hit(
                    target,
                    url=response.url,
                    kind="direct",
                    title=_title(response.body, response.url),
                    snippet=_snippet(text, matched, _title(response.body)),
                    matched=matched,
                    confidence=0.9,
                    evidence_id=evidence_id,
                    metadata={"http_status": response.status, "bytes": len(response.body)},
                )
            )
        return hits


class WaybackCollector(BaseCollector):
    name = "wayback"
    kind = "archive"

    def available(self, target: ExposureTarget) -> tuple[bool, str]:
        return (bool(target.urls), "no URLs supplied for archive lookup")

    def collect(self, target: ExposureTarget) -> list[ExposureHit]:
        hits: list[ExposureHit] = []
        for original in target.urls[:10]:
            query = (
                "https://web.archive.org/cdx/search/cdx?url="
                f"{quote(original, safe='')}&output=json&filter=statuscode:200"
                "&collapse=digest&limit=8"
            )
            try:
                response = self.http.get(query, check_robots=False)
            except (FetchError, UnsafeUrlError):
                continue
            if response.status != 200:
                continue
            try:
                rows = json.loads(response.text)
            except json.JSONDecodeError:
                continue
            if not isinstance(rows, list) or len(rows) <= 1:
                continue
            header, *records = rows
            indexes = {str(value): index for index, value in enumerate(header)}
            for record in records[:5]:
                timestamp = str(record[indexes.get("timestamp", 1)])
                archived_url = str(record[indexes.get("original", 2)])
                snapshot = f"https://web.archive.org/web/{timestamp}id_/{archived_url}"
                try:
                    page = self.http.get(snapshot, check_robots=False)
                except (FetchError, UnsafeUrlError):
                    continue
                if page.status >= 400:
                    continue
                text = self._extract_text(page.body, "archive.html")
                matched = _match(target, f"{archived_url}\n{text}")
                if not matched:
                    continue
                evidence_id = _store(
                    self.store,
                    page.body,
                    source=f"exposure:wayback:{snapshot}",
                    content_type=page.content_type or "text/html",
                )
                hits.append(
                    self._hit(
                        target,
                        url=snapshot,
                        kind="archive",
                        title=_title(page.body, archived_url),
                        snippet=_snippet(text, matched, _title(page.body)),
                        matched=matched,
                        confidence=0.8,
                        first_seen=timestamp,
                        last_seen=timestamp,
                        evidence_id=evidence_id,
                        metadata={"original_url": archived_url, "snapshot": timestamp},
                    )
                )
        return hits


class SearchApiCollector(BaseCollector):
    name = "search"
    kind = "search"

    def _provider(self) -> tuple[str, str] | None:
        serper = getattr(self.settings, "serper_api_key", None)
        brave = getattr(self.settings, "brave_api_key", None)
        if serper:
            return "serper", serper
        if brave:
            return "brave", brave
        return None

    def available(self, target: ExposureTarget) -> tuple[bool, str]:
        if not self._provider():
            return False, "set ERASUREPROOF_SERPER_API_KEY or ERASUREPROOF_BRAVE_API_KEY"
        return (bool(target.query_terms()), "no query terms")

    def collect(self, target: ExposureTarget) -> list[ExposureHit]:
        provider = self._provider()
        if provider is None:
            return []
        name, key = provider
        hits: list[ExposureHit] = []
        limit = int(getattr(self.settings, "exposure_max_queries", 6))
        queries = [f'"{term}"' for term in target.query_terms()[:limit]]
        for query in queries:
            try:
                if name == "serper":
                    response = self.http.post_json(
                        "https://google.serper.dev/search",
                        {"q": query, "num": 10},
                        {"X-API-KEY": key},
                    )
                else:
                    response = self.http.get(
                        "https://api.search.brave.com/res/v1/web/search?"
                        f"q={quote(query)}&count=10",
                        headers={"X-Subscription-Token": key},
                        check_robots=False,
                    )
            except (FetchError, UnsafeUrlError):
                continue
            if response.status != 200:
                continue
            try:
                payload = json.loads(response.text)
            except json.JSONDecodeError:
                continue
            evidence_id = _store(
                self.store,
                response.body,
                source=f"exposure:{name}:{query}",
                content_type="application/json",
            )
            for item in _search_results(name, payload):
                url = str(item.get("url", ""))
                title = str(item.get("title", ""))
                snippet = str(item.get("snippet", ""))
                matched = _match(target, f"{url}\n{title}\n{snippet}")
                if not matched:
                    continue
                hits.append(
                    self._hit(
                        target,
                        url=url,
                        kind="search",
                        title=title or url,
                        snippet=_snippet(f"{title}\n{snippet}", matched, title),
                        matched=matched,
                        confidence=0.65,
                        evidence_id=evidence_id,
                        metadata={
                            "query": mask_identifier(query.strip('"')),
                            "provider": name,
                        },
                    )
                )
        return hits


def _search_results(provider: str, payload: dict) -> list[dict[str, Any]]:
    if provider == "serper":
        return [
            {
                "url": item.get("link", ""),
                "title": item.get("title", ""),
                "snippet": item.get("snippet", ""),
            }
            for item in payload.get("organic", [])
            if isinstance(item, dict)
        ]
    results = payload.get("web", {}).get("results", [])
    return [
        {
            "url": item.get("url", ""),
            "title": item.get("title", ""),
            "snippet": item.get("description", ""),
        }
        for item in results
        if isinstance(item, dict)
    ]


class HibpCollector(BaseCollector):
    name = "hibp"
    kind = "breach"

    def available(self, target: ExposureTarget) -> tuple[bool, str]:
        if not getattr(self.settings, "hibp_api_key", None):
            return False, "set ERASUREPROOF_HIBP_API_KEY"
        return (bool(target.emails()), "no email address")

    def collect(self, target: ExposureTarget) -> list[ExposureHit]:
        key = getattr(self.settings, "hibp_api_key", None)
        if not key or not target.emails():
            return []
        email = target.emails()[0]
        response = self.http.get(
            f"https://haveibeenpwned.com/api/v3/breachedaccount/{quote(email)}"
            "?truncateResponse=false",
            headers={"hibp-api-key": key, "User-Agent": "ErasureProof-Exposure"},
            check_robots=False,
        )
        if response.status == 404:
            return []
        if response.status != 200:
            self.errors.append(f"HIBP lookup failed with HTTP {response.status}")
            return []
        evidence_id = _store(
            self.store,
            response.body,
            source=f"exposure:hibp:{email}",
            content_type="application/json",
        )
        try:
            breaches = json.loads(response.text)
        except json.JSONDecodeError:
            return []
        hits: list[ExposureHit] = []
        for breach in breaches[:25]:
            name = str(breach.get("Name") or breach.get("Title") or "breach")
            date = str(breach.get("BreachDate") or "")
            classes = ", ".join(str(item) for item in breach.get("DataClasses", []))
            hits.append(
                self._hit(
                    target,
                    url=f"https://haveibeenpwned.com/PwnedWebsites#{quote(name)}",
                    kind="breach",
                    title=f"Breach: {name}",
                    snippet=f"Breach date {date}. Exposed data classes: {classes}.",
                    matched=[email],
                    confidence=0.95,
                    first_seen=date or None,
                    last_seen=date or _now(),
                    evidence_id=evidence_id,
                    metadata={"breach": name, "data_classes": classes},
                )
            )
        return hits


class GithubCollector(BaseCollector):
    name = "github"
    kind = "code"

    def _token(self) -> str | None:
        return getattr(self.settings, "github_token", None)

    def available(self, target: ExposureTarget) -> tuple[bool, str]:
        if not self._token():
            return False, "set ERASUREPROOF_GITHUB_TOKEN for code search"
        return (bool(target.emails() or target.usernames), "no email or username")

    def collect(self, target: ExposureTarget) -> list[ExposureHit]:
        token = self._token()
        if not token:
            return []
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        hits: list[ExposureHit] = []
        for email in target.emails():
            response = self.http.get(
                f"https://api.github.com/search/code?q={quote(email)}",
                headers=headers,
                check_robots=False,
            )
            if response.status != 200:
                continue
            evidence_id = _store(
                self.store,
                response.body,
                source=f"exposure:github:code:{email}",
                content_type="application/json",
            )
            try:
                payload = json.loads(response.text)
            except json.JSONDecodeError:
                continue
            for item in payload.get("items", [])[:10]:
                url = str(item.get("html_url", ""))
                repo = str(item.get("repository", {}).get("full_name", ""))
                hits.append(
                    self._hit(
                        target,
                        url=url,
                        kind="code",
                        title=f"Public code match in {repo}",
                        snippet=f"Repository: {repo}. Review the file and remove the identifier.",
                        matched=[email],
                        confidence=0.75,
                        evidence_id=evidence_id,
                        metadata={"repository": repo},
                    )
                )
        for username in target.usernames:
            handle = username.lstrip("@")
            response = self.http.get(
                f"https://api.github.com/users/{quote(handle)}",
                headers=headers,
                check_robots=False,
            )
            if response.status != 200:
                continue
            evidence_id = _store(
                self.store,
                response.body,
                source=f"exposure:github:profile:{handle}",
                content_type="application/json",
            )
            try:
                payload = json.loads(response.text)
            except json.JSONDecodeError:
                continue
            hits.append(
                self._hit(
                    target,
                    url=str(payload.get("html_url", f"https://github.com/{handle}")),
                    kind="profile",
                    title=f"GitHub profile: {handle}",
                    snippet="Public GitHub profile found; review linked email and repositories.",
                    matched=[username],
                    confidence=0.8,
                    evidence_id=evidence_id,
                    last_seen=payload.get("updated_at"),
                    metadata={"login": handle},
                )
            )
        return hits


class GravatarCollector(BaseCollector):
    name = "gravatar"
    kind = "profile"

    def available(self, target: ExposureTarget) -> tuple[bool, str]:
        return (bool(target.emails()), "no email address")

    def collect(self, target: ExposureTarget) -> list[ExposureHit]:
        hits: list[ExposureHit] = []
        for email in target.emails():
            digest = hashlib.sha256(email.encode("utf-8")).hexdigest()
            url = f"https://gravatar.com/{digest}.json"
            try:
                response = self.http.get(url, check_robots=False)
            except (FetchError, UnsafeUrlError):
                continue
            if response.status != 200:
                continue
            evidence_id = _store(
                self.store,
                response.body,
                source=f"exposure:gravatar:{digest}",
                content_type="application/json",
            )
            try:
                payload = json.loads(response.text)
            except json.JSONDecodeError:
                payload = {}
            entry = payload.get("entry", [{}])
            profile = entry[0] if isinstance(entry, list) and entry else {}
            hits.append(
                self._hit(
                    target,
                    url=f"https://gravatar.com/{digest}",
                    kind="profile",
                    title=str(profile.get("displayName") or "Gravatar profile"),
                    snippet=str(profile.get("aboutMe") or "Public Gravatar profile exists.")[:240],
                    matched=[email],
                    confidence=0.7,
                    evidence_id=evidence_id,
                    metadata={"profile_url": profile.get("profileUrl", "")},
                )
            )
        return hits


class UsernameCollector(BaseCollector):
    name = "username"
    kind = "profile"

    def available(self, target: ExposureTarget) -> tuple[bool, str]:
        return (bool(target.usernames), "no usernames supplied")

    def collect(self, target: ExposureTarget) -> list[ExposureHit]:
        hits: list[ExposureHit] = []
        for username in target.usernames:
            handle = username.lstrip("@")
            for url, api in (
                (f"https://github.com/{handle}", f"https://api.github.com/users/{quote(handle)}"),
                (
                    f"https://keybase.io/{handle}",
                    f"https://keybase.io/_/api/1.0/user/lookup.json?username={quote(handle)}",
                ),
            ):
                try:
                    response = self.http.get(api, check_robots=False)
                except (FetchError, UnsafeUrlError):
                    continue
                if response.status != 200:
                    continue
                evidence_id = _store(
                    self.store,
                    response.body,
                    source=f"exposure:{self.name}:{url}",
                    content_type="application/json",
                )
                hits.append(
                    self._hit(
                        target,
                        url=url,
                        kind="profile",
                        title=f"Public profile match: {handle}",
                        snippet=f"Public account found at {url}; review linked identity data.",
                        matched=[username],
                        confidence=0.7,
                        evidence_id=evidence_id,
                        metadata={"username": handle},
                    )
                )
        return hits


COLLECTOR_CLASSES: dict[str, type[BaseCollector]] = {
    "direct": DirectUrlCollector,
    "wayback": WaybackCollector,
    "search": SearchApiCollector,
    "hibp": HibpCollector,
    "github": GithubCollector,
    "gravatar": GravatarCollector,
    "username": UsernameCollector,
}

DEFAULT_COLLECTORS = ["direct", "wayback", "search", "hibp", "github", "gravatar", "username"]


def normalise_values(target: ExposureTarget) -> dict[str, list[str]]:
    values: dict[str, list[str]] = {}
    if target.email:
        values["email"] = [normalize_value(target.email, IdentifierType.EMAIL)]
    if target.phone:
        values["phone"] = [normalize_value(target.phone, IdentifierType.PHONE)]
    if target.name:
        values["name"] = [target.name]
    if target.usernames:
        values["username"] = list(target.usernames)
    if target.urls:
        values["url"] = list(target.urls)
    return values


def mask_values(values: dict[str, list[str]]) -> dict[str, list[str]]:
    return {
        kind: [mask_identifier(value, kind) for value in items]
        for kind, items in values.items()
    }
