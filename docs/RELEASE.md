# Release v1.1.0

**Status: stable.** This is the first tagged public release of ErasureProof.

- Release date: 2026-10-28
- Published: 2026-10-29
- Tag: [`v1.1.0`](https://github.com/dsk-dev-ai/erasureproof/releases/tag/v1.1.0) at `3866e38`
- API, console, and SDK version: `1.1.0`
- License: Apache-2.0

## Release gate

| Check | Result |
| --- | --- |
| `make check` (ruff, pytest, SDK compile, console typecheck/build) | Pass: 80 tests passed, 1 skipped |
| GitHub Actions `ci.yml` on `main` and tag `v1.1.0` | Pass |
| Production Docker image build | Pass |
| Docker smoke test | Health, readiness, docs, console, SPA deep link, and demo seed returned `200` |
| Docker end-to-end audit | `COMPLETE`, 13 verification checks, 64-character signature |
| Ledger and attestation verification | Ledger `OK` (34 entries); attestation `VALID` |
| Production configuration guard | Startup rejected disabled authentication and the default attestation key |
| Production auth smoke test | Unauthenticated request `401`; authenticated request `200`; sandbox `201` |
| Hosted API | `/healthz` returns `1.1.0` against PostgreSQL |
| Hosted sandbox and audit | Sandbox created, audit completed, evidence attributed, attestation and ledger verified |
| Hosted console | Landing, console, API-key management, and overview rendered with correct percentage metrics |
| README screenshots | Refreshed from the hosted deployment at 1600 px; overview captured full-page with status mix, findings, policies, and ledger |

## Stable-release decision

The release is stable. No authentication, authorization, tenant-isolation,
evidence-integrity, attestation, ledger, or data-loss defects were found during
the release pass. One presentation defect was found during hosted smoke testing:
the overview multiplied already-percentage API values by 100. It was fixed,
rebuilt, redeployed, and rechecked before the tag was created.

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
