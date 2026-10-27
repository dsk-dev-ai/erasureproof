# Changelog

All notable changes are recorded here. ErasureProof follows semantic versioning.

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
