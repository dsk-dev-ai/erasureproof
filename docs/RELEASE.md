# Release v1.1.2

**Status: stable.** This security and correctness patch hardens deletion-status
decisions, evidence isolation, path handling, and concurrent mutation safety.

- Release date: 2026-10-31
- Published: 2026-10-31
- Tag: [`v1.1.2`](https://github.com/dsk-dev-ai/erasureproof/releases/tag/v1.1.2)
- API, console, and SDK version: `1.1.2`
- License: Apache-2.0
- PyPI: [`erasureproof`](https://pypi.org/project/erasureproof/1.1.2/) and
  [`erasureproof-sdk`](https://pypi.org/project/erasureproof-sdk/1.1.2/)
- Previous release: [`v1.1.1`](https://github.com/dsk-dev-ai/erasureproof/releases/tag/v1.1.1)

## Release gate

| Check | Result |
| --- | --- |
| `make check` (ruff, pytest, SDK compile, console typecheck/build) | Pass: 89 tests passed, 1 skipped |
| `make package-check` (both sdists/wheels, twine metadata) | Pass |
| GitHub Actions `ci.yml` on `main` | Pass |
| PyPI trusted-publishing workflow | Pass: both packages published |
| PyPI clean install | Pass: core demo `COMPLETE` with 13/13 checks; SDK imports as `1.1.2` |
| Hosted API | `/version` and `/readyz` return `1.1.2`; all readiness checks `ok` |
| GitHub release | [`v1.1.2`](https://github.com/dsk-dev-ai/erasureproof/releases/tag/v1.1.2) published |

## Release decision

This is a patch release. It fixes completion-status trust, evidence provenance
and tenant isolation, filesystem path handling, unsafe inline evidence
rendering, cross-process mutation races, API key rotation atomicity, and
unbounded backup decompression.

No API routes or response schemas were removed. Evidence is now served as an
attachment rather than inline, and evidence metadata includes an optional
`tenant_id`. Existing request-scoped evidence remains readable by its tenant.

The console remains a private npm workspace and is not published to npm. It is
built into the Python deployment image and served by FastAPI.

## Deployment caveats

These are operational limits, not release blockers:

- The public hosted demo runs on Render's free tier. Evidence and ledger files
  live on an ephemeral filesystem, so use persistent disk or object storage for
  durable production evidence.
- The hosted database runs on Neon Free. Neon compute, storage, and egress
  limits apply; use a paid database for production retention, availability, or
  capacity guarantees.
- Self-service sandbox remediation approval is disabled to keep the public demo
  useful. Enable `ERASUREPROOF_REQUIRE_REMEDIATION_APPROVAL` for production
  destructive runs.
- The hosted demo is rate-limited and shares a single free instance. Use the
  documented Docker, Compose, or Kubernetes paths for production capacity.
