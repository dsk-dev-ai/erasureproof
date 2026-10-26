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
    if args.json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    return 0 if result.status == "COMPLETE" else 1


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
    demo.set_defaults(func=_cmd_demo)

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
