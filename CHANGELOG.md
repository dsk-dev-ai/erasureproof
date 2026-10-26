# Changelog

All notable changes are recorded here. ErasureProof follows semantic versioning.

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
