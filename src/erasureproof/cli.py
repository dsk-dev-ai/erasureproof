"""Command-line entry point."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import get_settings


def _cmd_demo(args: argparse.Namespace) -> int:
    from .demo import run_demo

    result = run_demo()
    if args.json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        return 0 if result.status == "COMPLETE" else 1
    print(f"request:       {result.request_id}")
    print(f"status:        {result.status}")
    print(f"findings:      {len(result.plan.findings())}")
    print(f"remediation:   {'applied' if result.remediation_applied else 'skipped'}")
    print(f"actions:       {len(result.actions)}")
    passed = sum(1 for verification in result.verifications if verification.passed)
    print(f"verifications: {passed}/{len(result.verifications)} passed")
    print(f"ledger head:   {result.ledger_head}")
    if result.attestation:
        print(f"attestation:   {result.attestation.path}")
    if args.graph:
        from .core.graph import build_step_graph

        print()
        print(build_step_graph(result.plan).to_mermaid())
    return 0 if result.status == "COMPLETE" else 1


def _cmd_scan(args: argparse.Namespace) -> int:
    from datetime import datetime, timezone

    from .evidence.store import EvidenceStore
    from .intelligence.extract import ExtractionLimits
    from .intelligence.scanner import scan_directory
    from .models.domain import Identifier, IdentifierType, SubjectGraph

    settings = get_settings()
    identifiers = []
    if args.email:
        identifiers.append(Identifier(IdentifierType.EMAIL, args.email, source="cli"))
    if args.phone:
        identifiers.append(Identifier(IdentifierType.PHONE, args.phone, source="cli"))
    subject = SubjectGraph(user_id=args.user_id or "cli", identifiers=identifiers)
    store = EvidenceStore(settings.evidence_dir or settings.data_dir / "evidence")
    as_of = None
    if args.as_of:
        as_of = datetime.fromisoformat(args.as_of)
        if as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=timezone.utc)
    report = scan_directory(
        args.path,
        subject=subject,
        names=[args.name] if args.name else [],
        store=store,
        limits=ExtractionLimits(ocr=not args.no_ocr),
        include_all=args.include_all,
        include_hidden=args.hidden,
        max_files=args.max_files,
        as_of=as_of,
    )
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
        return 0
    print(f"scanned:       {report.scanned}")
    print(f"matched files: {len(report.matched_files)}")
    print(f"severity:      {report.severity} ({report.risk_score}/100)")
    for item in report.matched_files[:20]:
        print(f"  {item.path}  [{item.mime}]  matches={item.matched_count}")
    return 0


def _cmd_exposure(args: argparse.Namespace) -> int:
    from .evidence.ledger import EvidenceLedger
    from .evidence.store import EvidenceStore
    from .exposure.models import ExposureTarget
    from .exposure.service import ExposureService

    settings = get_settings()
    store = EvidenceStore(settings.evidence_dir or settings.data_dir / "evidence")
    ledger = EvidenceLedger(settings.ledger_path or settings.data_dir / "ledger.jsonl")
    target = ExposureTarget(
        email=args.email,
        phone=args.phone,
        name=args.name,
        usernames=args.username or [],
        urls=args.url or [],
    )
    if not target.all_values() and not target.urls:
        print("error: supply at least one identifier or URL", file=sys.stderr)
        return 2
    try:
        report = ExposureService(settings, store, ledger).scan(
            target,
            collectors=args.collector,
            authorized=args.authorized,
        )
    except PermissionError as exc:
        print(f"denied: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
        return 0
    print(f"hits:          {len(report.hits)}")
    print(f"severity:      {report.severity} ({report.risk_score}/100)")
    print(f"report:        {report.report_evidence_id}")
    for hit in report.hits[:25]:
        print(f"  [{hit.severity}] {hit.kind}: {hit.url}")
    for error in report.errors:
        print(f"  warning: {error}", file=sys.stderr)
    return 0


def _cmd_graph(args: argparse.Namespace) -> int:
    from .core.graph import build_step_graph, plan_from_dict

    data = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    graph = build_step_graph(plan_from_dict(data))
    if args.format == "mermaid":
        print(graph.to_mermaid())
    elif args.format == "dot":
        print(graph.to_dot())
    else:
        print(json.dumps(graph.to_dict(), indent=2, ensure_ascii=False))
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run(
        "erasureproof.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
    return 0


def _cmd_ledger_verify(args: argparse.Namespace) -> int:
    from .evidence.ledger import EvidenceLedger

    settings = get_settings()
    ledger = EvidenceLedger(args.path or settings.ledger_path)
    valid, detail = ledger.verify()
    print(f"ledger: {'OK' if valid else 'BROKEN'} - {detail}")
    return 0 if valid else 1


def _cmd_attestation_verify(args: argparse.Namespace) -> int:
    from .core.attestation import AttestationService

    settings = get_settings()
    service = AttestationService(
        settings.attestation_key,
        settings.attestation_dir or ".erasureproof/attestations",
    )
    valid, payload = service.verify_file(Path(args.path))
    print(f"signature: {'VALID' if valid else 'INVALID'}")
    if payload:
        print(f"request:   {payload.get('request_id')}")
        print(f"status:    {payload.get('status')}")
    return 0 if valid else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="erasureproof", description="Proof-of-erasure platform")
    subparsers = parser.add_subparsers(dest="command", required=True)

    demo = subparsers.add_parser("demo", help="run the seeded end-to-end demo")
    demo.add_argument("--json", action="store_true", help="print the full result as JSON")
    demo.add_argument("--graph", action="store_true", help="print the remediation DAG as Mermaid")
    demo.set_defaults(func=_cmd_demo)

    scan = subparsers.add_parser("scan", help="scan a directory for subject identifiers")
    scan.add_argument("path")
    scan.add_argument("--email")
    scan.add_argument("--phone")
    scan.add_argument("--name")
    scan.add_argument("--user-id")
    scan.add_argument("--include-all", action="store_true", help="report files without matches")
    scan.add_argument("--hidden", action="store_true", help="include hidden files")
    scan.add_argument("--no-ocr", action="store_true", help="disable OCR")
    scan.add_argument("--max-files", type=int, default=5000)
    scan.add_argument("--as-of", help="ISO timestamp cutoff")
    scan.add_argument("--json", action="store_true")
    scan.set_defaults(func=_cmd_scan)

    exposure = subparsers.add_parser(
        "exposure", help="passively check authorized public sources for exposure"
    )
    exposure.add_argument("--email")
    exposure.add_argument("--phone")
    exposure.add_argument("--name")
    exposure.add_argument("--username", action="append")
    exposure.add_argument("--url", action="append")
    exposure.add_argument("--collector", action="append")
    exposure.add_argument(
        "--authorized",
        action="store_true",
        help="confirm you are authorized to check these identifiers",
    )
    exposure.add_argument("--json", action="store_true")
    exposure.set_defaults(func=_cmd_exposure)

    graph = subparsers.add_parser("graph", help="render a stored plan as a DAG")
    graph.add_argument("plan", help="path to a plan/result JSON file")
    graph.add_argument("--format", choices=["json", "mermaid", "dot"], default="mermaid")
    graph.set_defaults(func=_cmd_graph)

    serve = subparsers.add_parser("serve", help="run the HTTP API")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true")
    serve.set_defaults(func=_cmd_serve)

    ledger = subparsers.add_parser("ledger", help="ledger utilities")
    ledger_sub = ledger.add_subparsers(dest="ledger_command", required=True)
    verify = ledger_sub.add_parser("verify", help="verify the hash chain")
    verify.add_argument("--path", default=None)
    verify.set_defaults(func=_cmd_ledger_verify)

    attestation = subparsers.add_parser("attestation", help="attestation utilities")
    attestation_sub = attestation.add_subparsers(dest="attestation_command", required=True)
    attestation_verify = attestation_sub.add_parser("verify", help="verify a signed attestation")
    attestation_verify.add_argument("path")
    attestation_verify.set_defaults(func=_cmd_attestation_verify)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
