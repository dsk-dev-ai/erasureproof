"""Exposure scan orchestration, scoring and evidence recording."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

from .collectors import COLLECTOR_CLASSES, DEFAULT_COLLECTORS, BaseCollector
from .http import HttpClient
from .models import ExposureReport, ExposureTarget, score_report


class ExposureService:
    def __init__(
        self,
        settings: Any,
        store: Any,
        ledger: Any | None = None,
        http: HttpClient | None = None,
    ) -> None:
        self.settings = settings
        self.store = store
        self.ledger = ledger
        self.http = http or HttpClient(
            timeout=float(getattr(settings, "exposure_timeout_seconds", 15)),
            max_bytes=int(getattr(settings, "exposure_max_bytes", 2_000_000)),
            user_agent=str(
                getattr(
                    settings,
                    "exposure_user_agent",
                    "ErasureProof/1.0 (+https://github.com/dsk-dev-ai/erasureproof)",
                )
            ),
            rate_limit_seconds=float(
                getattr(settings, "exposure_rate_limit_seconds", 1.0)
            ),
        )

    def _selected(self, collectors: Iterable[str] | None) -> list[str]:
        if collectors is None:
            return list(DEFAULT_COLLECTORS)
        result: list[str] = []
        for item in collectors:
            name = str(item).strip().lower()
            if name and name not in result:
                result.append(name)
        return result

    def scan(
        self,
        target: ExposureTarget,
        collectors: Iterable[str] | None = None,
        authorized: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> ExposureReport:
        selected = self._selected(collectors)
        network_selected = bool(selected)
        if network_selected and not authorized:
            raise PermissionError(
                "exposure discovery requires explicit authorization for these identifiers"
            )
        if network_selected and not bool(getattr(self.settings, "exposure_enabled", False)):
            raise PermissionError(
                "exposure discovery is disabled; set ERASUREPROOF_EXPOSURE_ENABLED=true"
            )

        report = ExposureReport(
            target=target,
            generated_at=datetime.now(timezone.utc),
            collectors=selected,
            authorized=authorized,
        )
        hits = []
        seen: set[tuple[str, str, str]] = set()
        for name in selected:
            collector_class = COLLECTOR_CLASSES.get(name)
            if collector_class is None:
                report.errors.append(f"{name}: unknown collector")
                continue
            collector: BaseCollector = collector_class(self.settings, self.store, self.http)
            available, reason = collector.available(target)
            if not available:
                report.errors.append(f"{name}: {reason}")
                continue
            try:
                collected = collector.collect(target)
            except Exception as exc:  # collectors are isolated
                report.errors.append(f"{name}: {type(exc).__name__}: {exc}")
                continue
            finally:
                report.errors.extend(f"{name}: {item}" for item in collector.errors)
            for hit in collected:
                key = (hit.collector, hit.kind, hit.url)
                if key in seen:
                    continue
                seen.add(key)
                hits.append(hit)

        report.hits = sorted(
            hits,
            key=lambda hit: (
                {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}.get(hit.severity, 9),
                -hit.confidence,
                hit.url,
            ),
        )
        report.risk_score, report.severity, report.recommendations = score_report(report.hits)

        if self.store is not None:
            record = self.store.put(
                report.to_dict(),
                source="exposure:report",
                captured_at=report.generated_at,
                content_type="application/json",
            )
            report.report_evidence_id = record.evidence_id

        if self.ledger is not None:
            self.ledger.append(
                "exposure.scanned",
                f"exposure_{report.generated_at.strftime('%Y%m%dT%H%M%SZ')}",
                {
                    "collectors": selected,
                    "hits": len(report.hits),
                    "risk_score": report.risk_score,
                    "severity": report.severity,
                    "report_evidence_id": report.report_evidence_id,
                    "authorized": authorized,
                    **(metadata or {}),
                },
            )
        return report
