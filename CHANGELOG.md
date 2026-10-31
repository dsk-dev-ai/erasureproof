# Changelog

All notable changes are recorded here. ErasureProof follows semantic versioning.

## Unreleased

No unreleased changes.

## 1.1.2 — 2026-10-31

A security and correctness patch for deletion-status decisions, evidence
isolation, path handling, and concurrent mutation safety.

### Fixed

- A run can no longer report `COMPLETE` when discovery fails, verification
  fails, or post-remediation discovery finds resources, flows, or backups that
  were not in the plan.
- Local S3-compatible object stores reject traversal and symlink escapes during
  discovery and remediation.
- Evidence metadata is scoped by request and tenant, so identical bytes from
  different audits no longer overwrite each other's provenance.
- Exposure evidence is tenant-scoped and visible to the tenant that created it.
- Evidence IDs, digests, stored paths, and attestation request IDs are validated
  before filesystem access.
- Evidence downloads are served as sandboxed attachments instead of inline
  active content.
- Ledger appends and control-plane flow/restore mutations are serialised across
  processes.
- API key rotation issues the replacement and revokes the previous key in one
  locked transaction.
- Backup verification bounds manifest and member decompression.

### Changed

- Version bumped to 1.1.2 across the API, console, and SDK.

## 1.1.1 — 2026-10-30

The hosted deployment now uses Neon Free PostgreSQL, and both the core package
and Python SDK are published on PyPI with trusted publishing.

### Added

- PyPI packages `erasureproof` and `erasureproof-sdk`, with package checks in CI,
  a tag-triggered trusted-publishing workflow, and install instructions for the
  core CLI and SDK.
- Free deployment profile using Render Free for the web service and Neon Free
  PostgreSQL for durable relational data, with no credit card requirement.

### Changed

- The Render Blueprint now prompts for an external `ERASUREPROOF_DATABASE_URL`
  instead of provisioning a temporary 30-day Render Postgres database.
- The hosted demo now uses Neon Free; the legacy Render Postgres was removed
  after the data restore and live application were verified.
- Core and SDK releases use separate GitHub environments (`pypi` and
  `pypi-sdk`) for PyPI trusted publishing.
- The console remains a private npm workspace and is not published to npm; it is
  built into the Python deployment image.

### Fixed

- PostgreSQL connections enable pre-ping so stale connections are replaced after
  Neon scale-to-zero or a Render restart.

## 1.1.0 — 2026-10-28

The first tagged stable release. It adds the hosted developer experience,
self-service sandbox onboarding, tenant API keys, and the deployment surface
needed to run ErasureProof as a shared service.

### Added

- Self-service sandbox onboarding with isolated tenants, seeded connectors, a
  sample deletion request, per-IP/global quotas, and one-time administrator keys.
- Tenant API key lifecycle: hashed storage, roles, expiry, rotation, revocation,
  limits, and audit events.
- Console API key management page and one-time sandbox onboarding dialog.
- Hosted console onboarding, developer quickstart, and live deployment links.
- Python SDK, API reference, Render blueprint, and deployment guide.
- Release banner, README quickstart, release evidence, CI badge, and GitHub
  Sponsors support.

### Fixed

- Connector evidence is now attributed to the audited request, so tenant-scoped
  evidence listing and overview counts include discovery snapshots.
- PostgreSQL URLs are normalized to the Psycopg driver automatically.
- Sandbox handoff redirects stay inside the console base path.
- Overview pass-rate and attestation-coverage metrics no longer multiply
  already-percentage API values by 100.

### Changed

- Version bumped to 1.1.0 across the API, console, and SDK.

## 1.0.0

### Added

- API-key and OIDC authentication with viewer, operator, and administrator
  roles plus server-side tenant isolation on every endpoint.
- Single-use, time-limited remediation approvals with separation of duties.
- Tamper-evident operational audit events with JSON listings and tenant-scoped
  CSV export.
- Signed backup archives for evidence, ledger, attestations, and SQLite
  metadata, with verification and safe restore.
- Request IDs, per-IP rate limiting, Prometheus metrics, security headers,
  readiness checks, and production configuration validation.
- Console bearer-token management, authenticated evidence downloads, approval
  controls, and audit export.
- Kubernetes manifests with probes, HPA, ingress, shared storage, and network
  policy, plus a production Compose overlay.
- OIDC extra and cryptography in the development environment.

### Changed

- CORS no longer defaults to `*`; configure `ERASUREPROOF_CORS_ORIGINS`.
- Evidence metadata stores relative paths so restored data directories resolve
  existing objects.
- Connector configurations are redacted for secret-bearing keys in API output.
- Production startup fails when authentication is disabled or the default
  attestation key is still in use.
- Version bumped to 1.0.0 across the API, console, and documentation.

## 0.3.0

### Added

- Self-hosted Vite/React operations console served by FastAPI at `/console`.
- Landing page, overview dashboard, request audits, identity inventory, connector
  management, evidence and ledger inspection, passive exposure scanning,
  policy visibility, settings, and in-app documentation.
- Interactive remediation dependency graph with finding, remediation, and
  verification phases.
- Non-destructive demo workspace with audit, complete-erasure, access-request,
  and pending scenarios.
- Multi-stage Docker build that compiles the console and bundles the static
  assets with the Python runtime.
- SPA fallback, immutable asset caching, and a console build-presence check.

### Changed

- The API and console share one deployment and one origin; the console uses
  `/v1` by default and honors `VITE_API_URL`.
- Health checks use the root `/healthz` endpoint rather than `/v1`.
- Frontend pages are route-split to keep the initial bundle small.

## 0.2.0

### Added

- Content-addressed evidence store with PDF, OCR, Office, archive, SQLite, and
  metadata extraction.
- Authorized passive exposure discovery with SSRF and scope guardrails.
- Step dependency graph in JSON, Mermaid, and Graphviz DOT.
- Attestation issuance and hash-chained ledger verification.
- Docker image and CI workflow.

## 0.1.0

### Added

- Multilingual deletion-intent classification and identity resolution.
- SQL, object-store, filesystem, S3, and control-plane connectors.
- Policy engine, deterministic planner, verifier, and signed attestations.
- CLI demo, FastAPI service, and baseline test suite.
