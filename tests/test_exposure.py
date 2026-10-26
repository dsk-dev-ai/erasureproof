from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from erasureproof.evidence.ledger import EvidenceLedger
from erasureproof.evidence.store import EvidenceStore
from erasureproof.exposure.collectors import HibpCollector, SearchApiCollector
from erasureproof.exposure.http import HttpResponse, UnsafeUrlError, validate_url
from erasureproof.exposure.models import ExposureHit, ExposureTarget, score_report
from erasureproof.exposure.service import ExposureService


class FakeHttp:
    def __init__(self, responses: dict[str, HttpResponse]) -> None:
        self.responses = responses
        self.requests: list[tuple[str, str]] = []

    def get(self, url: str, headers=None, check_robots=True, allow_private=None):
        self.requests.append(("GET", url))
        return self.responses.get(url, HttpResponse(url=url, status=404))

    def post_json(self, url: str, payload, headers=None):
        self.requests.append(("POST", url))
        return self.responses[url]


def _settings(**overrides):
    values = {
        "exposure_enabled": True,
        "exposure_timeout_seconds": 1,
        "exposure_max_bytes": 1000,
        "exposure_user_agent": "test-agent",
        "exposure_rate_limit_seconds": 0,
        "serper_api_key": None,
        "brave_api_key": None,
        "github_token": None,
        "hibp_api_key": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_validate_url_blocks_local_and_private_targets() -> None:
    with pytest.raises(UnsafeUrlError):
        validate_url("http://localhost/robots.txt")
    with pytest.raises(UnsafeUrlError):
        validate_url("http://127.0.0.1/")
    with pytest.raises(UnsafeUrlError):
        validate_url("file:///etc/passwd")


def test_direct_scan_records_masked_evidence(tmp_path) -> None:
    url = "https://example.com/team"
    body = b"<html><title>Team</title><p>Alice alice@example.com</p></html>"
    fake = FakeHttp({url: HttpResponse(url=url, status=200, body=body)})
    store = EvidenceStore(tmp_path / "evidence")
    ledger = EvidenceLedger(tmp_path / "ledger.jsonl")
    service = ExposureService(_settings(), store, ledger, http=fake)

    report = service.scan(
        ExposureTarget(email="alice@example.com", urls=[url]),
        collectors=["direct"],
        authorized=True,
    )

    assert report.authorized is True
    assert len(report.hits) == 1
    assert report.hits[0].kind == "direct"
    assert report.hits[0].evidence_id.startswith("ev_")
    assert report.report_evidence_id.startswith("ev_")
    serialised = report.to_dict()
    assert serialised["hits"][0]["identifiers"] == ["a***@example.com"]
    assert serialised["authorized"] is True
    assert ledger.read()[-1].event == "exposure.scanned"


def test_scan_requires_authorization_and_enablement(tmp_path) -> None:
    service = ExposureService(
        _settings(exposure_enabled=False),
        EvidenceStore(tmp_path / "evidence"),
        EvidenceLedger(tmp_path / "ledger.jsonl"),
        http=FakeHttp({}),
    )
    target = ExposureTarget(email="alice@example.com", urls=["https://example.com"])

    with pytest.raises(PermissionError, match="authorization"):
        service.scan(target, collectors=["direct"])
    with pytest.raises(PermissionError, match="disabled"):
        service.scan(target, collectors=["direct"], authorized=True)


def test_hibp_collector_maps_breach_metadata(tmp_path) -> None:
    url = "https://haveibeenpwned.com/api/v3/breachedaccount/alice%40example.com?truncateResponse=false"
    payload = [
        {
            "Name": "ExampleBreach",
            "BreachDate": "2024-01-02",
            "DataClasses": ["Email addresses", "Passwords"],
        }
    ]
    fake = FakeHttp(
        {
            url: HttpResponse(
                url=url,
                status=200,
                headers={"content-type": "application/json"},
                body=json.dumps(payload).encode(),
            )
        }
    )
    collector = HibpCollector(
        _settings(hibp_api_key="key"),
        EvidenceStore(tmp_path / "evidence"),
        fake,
    )
    hits = collector.collect(ExposureTarget(email="alice@example.com"))
    assert len(hits) == 1
    assert hits[0].kind == "breach"
    assert hits[0].severity == "CRITICAL"
    assert hits[0].evidence_id.startswith("ev_")


def test_search_collector_accepts_serper_results(tmp_path) -> None:
    url = "https://google.serper.dev/search"
    payload = {
        "organic": [
            {
                "title": "Alice",
                "link": "https://example.com",
                "snippet": "alice@example.com",
            }
        ]
    }
    fake = FakeHttp(
        {
            url: HttpResponse(
                url=url,
                status=200,
                headers={"content-type": "application/json"},
                body=json.dumps(payload).encode(),
            )
        }
    )
    collector = SearchApiCollector(
        _settings(serper_api_key="key"),
        EvidenceStore(tmp_path / "evidence"),
        fake,
    )
    hits = collector.collect(ExposureTarget(email="alice@example.com"))
    assert len(hits) == 1
    assert hits[0].collector == "search"
    assert hits[0].url == "https://example.com"


def test_risk_scoring_escalates_breaches() -> None:
    hits = [
        ExposureHit(collector="hibp", kind="breach", url="https://example.com"),
        ExposureHit(collector="search", kind="search", url="https://example.org"),
    ]
    score, severity, recommendations = score_report(hits)
    assert score >= 60
    assert severity in {"HIGH", "CRITICAL"}
    assert any("credentials" in item for item in recommendations)
