# Release v1.1.1

**Status: stable.** This patch release moves the hosted deployment to Neon Free
and publishes the core CLI/API and Python SDK to PyPI.

- Release date: 2026-10-30
- Published: 2026-10-30
- Tag: [`v1.1.1`](https://github.com/dsk-dev-ai/erasureproof/releases/tag/v1.1.1)
- API, console, and SDK version: `1.1.1`
- License: Apache-2.0
- PyPI: [`erasureproof`](https://pypi.org/project/erasureproof/1.1.1/) and
  [`erasureproof-sdk`](https://pypi.org/project/erasureproof-sdk/1.1.1/)
- Previous release: [`v1.1.0`](https://github.com/dsk-dev-ai/erasureproof/releases/tag/v1.1.0)

## Release gate

| Check | Result |
| --- | --- |
| `make check` (ruff, pytest, SDK compile, console typecheck/build) | Pass: 80 tests passed, 1 skipped |
| `make package-check` (both sdists/wheels, twine metadata) | Pass |
| GitHub Actions `ci.yml` on `main` | Pass |
| PyPI trusted-publishing workflow | Pass: both packages published |
| PyPI clean install | Core demo `COMPLETE` with 13/13 verification checks; SDK import passed |
| Hosted API | `/version` returns `1.1.1`; `/readyz` reports `ok` against Neon PostgreSQL |
| Neon migration | Row counts matched; legacy Render Postgres deleted 2026-10-29 |

## Release decision

This is a patch release. No authentication, authorization, tenant-isolation,
evidence-integrity, attestation, or ledger behavior changed. The functional fix
enables PostgreSQL pre-ping so stale connections are replaced after Neon
scale-to-zero or a Render restart. The release also adds reproducible packaging
and trusted publishing for both PyPI projects.

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
