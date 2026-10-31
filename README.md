<p align="center">
  <img src="https://raw.githubusercontent.com/dsk-dev-ai/erasureproof/main/docs/assets/banner.svg" alt="ErasureProof — find every copy, prove every deletion" width="100%">
</p>

<h1 align="center">ErasureProof</h1>

<p align="center">
  <strong>Deletion is a promise. Prove it.</strong><br>
  Find every copy of a person's data, remediate in a safe order, and issue a signed, tamper-evident attestation.
</p>

<p align="center">
  <a href="https://erasureproof.onrender.com/healthz"><img src="https://img.shields.io/website?url=https%3A%2F%2Ferasureproof.onrender.com%2Fhealthz&label=live%20api&up_message=operational&down_message=offline&style=for-the-badge&color=14b8a6" alt="Live API status"></a>
  <a href="https://github.com/dsk-dev-ai/erasureproof/releases"><img src="https://img.shields.io/github/v/release/dsk-dev-ai/erasureproof?style=for-the-badge&color=14b8a6" alt="Latest release"></a>
  <a href="https://pypi.org/project/erasureproof/"><img src="https://img.shields.io/pypi/v/erasureproof?style=for-the-badge&color=14b8a6" alt="PyPI"></a>
  <a href="https://pypi.org/project/erasureproof-sdk/"><img src="https://img.shields.io/pypi/v/erasureproof-sdk?style=for-the-badge&color=14b8a6" alt="PyPI SDK"></a>
  <a href="https://github.com/dsk-dev-ai/erasureproof/actions/workflows/ci.yml"><img src="https://github.com/dsk-dev-ai/erasureproof/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/dsk-dev-ai/erasureproof/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-0ea5e9?style=for-the-badge" alt="Apache-2.0 license"></a>
  <a href="https://github.com/sponsors/dsk-dev-ai"><img src="https://img.shields.io/badge/sponsor-Support%20the%20project-db2777?style=for-the-badge" alt="Sponsor ErasureProof"></a>
</p>

<p align="center">
  <a href="https://erasureproof.onrender.com/console">Live console</a> ·
  <a href="https://erasureproof.onrender.com/docs">API documentation</a> ·
  <a href="https://github.com/dsk-dev-ai/erasureproof/releases/tag/v1.1.2">Release notes</a> ·
  <a href="https://github.com/dsk-dev-ai/erasureproof/tree/main/sdk/python">Python SDK</a> ·
  <a href="https://github.com/dsk-dev-ai/erasureproof/blob/main/docs/API.md">API reference</a> ·
  <a href="https://github.com/dsk-dev-ai/erasureproof/blob/main/docs/DEPLOY_RENDER.md">Deployment guide</a>
</p>

> [!TIP]
> **Try a live deletion audit in under a minute.** Create an isolated sandbox
> with a one-time API key. No installation, no production data, and a signed
> attestation at the end.

```bash
curl -s -X POST https://erasureproof.onrender.com/v1/onboarding/sandbox \
  -H 'content-type: application/json' \
  -d '{"workspace_name":"Acme privacy"}'
```

<p align="center">
  <a href="https://github.com/dsk-dev-ai/erasureproof/blob/main/docs/assets/landing.png">
    <img src="https://raw.githubusercontent.com/dsk-dev-ai/erasureproof/main/docs/assets/landing.png" alt="ErasureProof hosted console landing page" width="100%">
  </a>
</p>

<p align="center"><sub>The hosted operations console: deletion audits, remediation plans, evidence, and ledger verification. <a href="https://github.com/dsk-dev-ai/erasureproof/blob/main/docs/assets/landing.png">Open full size</a>.</sub></p>

ErasureProof is a deletion-audit and remediation engine. It reconstructs a
person's identity from current and historical identifiers, finds their records
across databases, replicas, search indexes, analytics, support systems, logs,
exports, archives and backups, applies your erasure policy, remediates in a safe
dependency order, verifies the result, and issues a signed, tamper-evident
attestation.

Deletion workflows usually report success because the primary database deleted a
row. ErasureProof treats those statuses as claims. It proves the state of every
copy at a point in time — including active sync jobs and restorable backups that
can recreate data after deletion.

## Why this exists

- **Ghost data is normal.** Replicas, search indexes, analytics pipelines,
  exports, support attachments and backups retain identifiers long after the
  source row is gone.
- **Workflow status is not evidence.** A `COMPLETE` badge does not prove that a
  person's data is absent or that retained records were properly redacted.
- **Regulators want proof.** A deletion request needs a defensible record of
  what was found, what was changed, what was deliberately retained, and how the
  final state was verified.

## How it works

```text
Request ──► Intent classifier ──► Identity graph (current + historical IDs)
                                        │
                                        ▼
                          Connector fan-out (read-only discovery)
                                        │
                                        ▼
                    Policy engine ──► Findings + ordered remediation plan
                                        │
                                        ▼
                 Flow/restore controls ──► Record remediation
                                        │
                                        ▼
                     Re-discovery ──► Verification ──► Signed attestation
                                                        + hash-chained ledger
```

1. **Intent.** Only an explicit, non-negated deletion request authorizes action.
   Access, correction, export, marketing opt-out and restriction requests are
   reported as `NOT_APPLICABLE`.
2. **Identity.** Current and historical emails, phones and email hashes are
   reunited into one subject graph, so old identifiers still found in logs and
   analytics are in scope.
3. **Discovery.** Connectors enumerate matching records, active data flows and
   restore points. The filesystem connector extracts PDF text, image OCR,
   Office/archive members, SQLite snapshots, EXIF and printable strings, so a
   match does not depend on a filename. Each snapshot is written to a
   content-addressed evidence store.
4. **Policy.** A YAML policy maps each category to `DELETE`, `REDACT`,
   `ANONYMIZE`, `RETAIN` or `TOMBSTONE`. Legal holds and retention obligations
   override erasure.
5. **Planning.** Findings cite evidence. Remediation disables flows and blocks
   restores first, then removes downstream copies before their source records.
   A dependency graph validates the order and exposes a critical path.
6. **Verification.** The engine re-discovers state after remediation and checks
   every expected outcome; it does not trust action success flags.
7. **Attestation.** The outcome, plan and verification results are canonicalised,
   signed with HMAC-SHA256 and committed to a SHA-256 hash-chained ledger.

## What ships in 1.1

| Prove the state | Remediate safely | Operate with confidence |
| --- | --- | --- |
| Identity graph over current and historical identifiers | Policy engine for delete, redact, anonymize, retain, and tombstone | API-key or OIDC auth with tenant isolation and roles |
| Evidence extraction for PDF, OCR, Office, archives, SQLite, logs, and images | Dependency-ordered plan that controls flows and restores first | Approval-gated destructive runs with separation of duties |
| Signed HMAC attestations plus a hash-chained ledger | Re-discovery and verification that never trusts action flags | Audit events, CSV export, signed backups, metrics, and probes |
| Interactive remediation DAG in JSON, Mermaid, or DOT | Built-in SQL, object-store, filesystem, S3, and control connectors | Hosted console, Python SDK, Docker, Compose, and Kubernetes |

- **Authentication and tenant isolation** with static API keys or OIDC,
  viewer/operator/administrator roles, and server-side tenant scoping.
- **Self-service onboarding** with isolated sandboxes, seeded connectors,
  one-time keys, per-IP quotas, and expiry.
- **Approval-gated remediation** where a second administrator authorizes a
  single-use, time-limited destructive run.
- **Tamper-evident auditing** with tenant-scoped CSV export and signed backups
  of evidence, the ledger, attestations, and metadata.
- **A hardened edge** with request IDs, per-IP rate limiting, Prometheus
  metrics, security headers, configurable CORS, readiness probes, and
  Kubernetes manifests.
- **A full console** for overview metrics, request audits, identity graphs,
  remediation plans, evidence inspection, ledger verification, policy review,
  API keys, and demo discovery.
- **Evidence intelligence** for PDFs, images, OCR, Office files, archives,
  SQLite snapshots, metadata, and free text.
- **Authorized exposure discovery** for public URLs, web archives, search APIs,
  breach metadata, and public profiles — passive checks only, disabled by
  default.
- **A step dependency graph** that validates ordering and renders as Mermaid,
  Graphviz DOT, JSON, or an interactive console view.

## Install

```bash
pip install erasureproof
```

Install database, OIDC, object-store, or workflow extras as needed:

```bash
pip install "erasureproof[postgres]"
pip install "erasureproof[oidc]"
pip install "erasureproof[s3]"
pip install "erasureproof[temporal]"
```

The core CLI is on [PyPI](https://pypi.org/project/erasureproof/). The
standalone Python client is published separately as
[`erasureproof-sdk`](https://pypi.org/project/erasureproof-sdk/):

```bash
pip install erasureproof-sdk
```

## Quickstart

For local development from source, use Python 3.10+ (3.11/3.12 recommended)
and `uv` or `pip`:

```bash
# with uv (recommended)
uv venv .venv
uv pip install --python .venv/bin/python -e ".[dev]"

# or with a standard virtualenv
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

Once installed from PyPI, run the demo directly with `erasureproof demo` or
`uvx erasureproof demo`.

### Run the end-to-end demo

```bash
.venv/bin/erasureproof demo
```

The demo seeds a fictional commerce platform (SQLite + local object bucket +
control plane), runs a GDPR erasure for `alice@example.com`, remediates every
copy, verifies the result and writes a signed attestation under
`.erasureproof/attestations/`. Expected output ends with `status: COMPLETE` and
all verification checks passing.

Useful follow-ups:

```bash
.venv/bin/erasureproof demo --json
.venv/bin/erasureproof demo --graph   # Mermaid step DAG
.venv/bin/erasureproof ledger verify
.venv/bin/erasureproof attestation verify .erasureproof/attestations/<request_id>.attestation.json

# Scan an export directory for current or historical identifiers.
.venv/bin/erasureproof scan ./exports --email alice@example.com --name "Alice Example"

# Render a stored plan/result as a graph.
.venv/bin/erasureproof graph result.json --format dot
```

### Run the API

```bash
.venv/bin/erasureproof serve --reload
# OpenAPI docs: http://localhost:8000/docs
```

Local development defaults to `ERASUREPROOF_AUTH_MODE=disabled`. Production
startup fails unless authentication is enabled and the attestation key is
changed. For a static-key deployment:

```bash
export ERASUREPROOF_ENVIRONMENT=production
export ERASUREPROOF_AUTH_MODE=api_key
export ERASUREPROOF_ATTESTATION_KEY="$(openssl rand -hex 32)"
export ERASUREPROOF_API_KEYS='[{"key":"replace-me","role":"admin","tenant_id":"*","subject":"admin"}]'
export ERASUREPROOF_REQUIRE_REMEDIATION_APPROVAL=true
export ERASUREPROOF_CORS_ORIGINS=https://erasureproof.example.com
```

Send the key as `Authorization: Bearer <key>` or `X-API-Key: <key>`. OIDC mode
validates RS256/384/512 tokens against the configured issuer, audience, and
JWKS URL; install the `oidc` extra.

### Run the web console

The console is a Vite + React application in `web/`. It ships a landing page, an
operations dashboard, request audits, a remediation dependency graph, identity
and connector views, evidence/ledger inspection, passive exposure scanning,
policy configuration, and built-in product documentation. The console is a
private npm workspace (`"private": true`) and is not published to npm; it is
built into the Python deployment image.

Install the console dependencies once, then run both processes from the repository root:

```bash
npm install --prefix web
npm run dev
# Console: http://localhost:5173
# API:     http://localhost:8000
```

`npm run dev` starts the FastAPI API (with reload) and the Vite console together.
Use `npm run dev:api` or `npm run dev:web` to start only one side. The root
scripts require an existing `.venv` created during installation.

For a production build served by FastAPI:

```bash
npm run build
.venv/bin/erasureproof serve
# Console: http://localhost:8000/console
```

The Vite build requires Node 22 or newer and uses `/console/` as its production
base. FastAPI serves hashed assets with immutable caching and falls back to
`index.html` for client routes.
Seed the non-destructive demo workspace from the landing page or with:

```bash
curl -X POST http://localhost:8000/v1/demo/seed
```

When authentication is enabled, open the key button in the console top bar (or
Settings → API access) and paste a bearer token. Evidence downloads use the same
authenticated request, so private artifacts never require a public URL.

### Hosted demo and developer API

The hosted demo runs at <https://erasureproof.onrender.com>: the console is at
`/console`, OpenAPI at `/docs`, and the API under `/v1`. Create a free isolated
sandbox with a one-time API key:

```bash
curl -s -X POST "$BASE_URL/v1/onboarding/sandbox" \
  -H 'content-type: application/json' \
  -d '{"workspace_name":"Acme privacy"}'
```

Use the returned key with the Python SDK:

```python
from erasureproof_sdk import create_sandbox

client, sandbox = create_sandbox("https://erasureproof.onrender.com")
run = client.run_request(sandbox["sample_request_id"], remediate=False)
print(run["status"], run["attestation"]["signature"])
```

See [`docs/API.md`](https://github.com/dsk-dev-ai/erasureproof/blob/main/docs/API.md) for endpoint, role, approval, and error
reference, and [`docs/DEPLOY_RENDER.md`](https://github.com/dsk-dev-ai/erasureproof/blob/main/docs/DEPLOY_RENDER.md) for the Render
deployment profile.

> [!WARNING]
> The hosted instance is an evaluation sandbox, not durable evidence storage.
> Render's free web filesystem is ephemeral, so evidence, ledger, attestation,
> and sandbox-connector files are lost on restart, deploy, or host migration.
> The hosted database is Neon Free in AWS US West (Oregon), with no 30-day
> database expiry. Neon's free compute, storage, and egress limits apply. The
> legacy Render Postgres was deleted after the migration was verified. For
> durable evidence, attach a persistent disk or shared volume. ErasureProof's
> evidence store is filesystem-backed; an object-store backend is not built in.

### Docker

```bash
docker compose up --build
# Console: http://localhost:8000/console
# API:     http://localhost:8000
# Docs:    http://localhost:8000/docs
```

That compose file is a local demo with authentication disabled. For a hardened
single-host deployment with an external PostgreSQL database, API-key auth,
required approvals, metrics token, and HSTS:

```bash
export ERASUREPROOF_DATABASE_URL='postgresql+psycopg://...'
export ERASUREPROOF_ATTESTATION_KEY="$(openssl rand -hex 32)"
export ERASUREPROOF_API_KEYS='[{"key":"...","role":"admin","tenant_id":"*","subject":"admin"}]'
export ERASUREPROOF_METRICS_TOKEN="$(openssl rand -hex 32)"
export ERASUREPROOF_CORS_ORIGINS='https://erasureproof.example.com'
docker compose -f docker-compose.production.yml up -d --build
```

The image uses a multi-stage build: Node builds the console, then the Python
runtime bundles the static assets with OCR and document tooling.

Create a tenant, register connectors, submit a request and run it:

```bash
curl -s localhost:8000/v1/tenants \
  -H 'content-type: application/json' \
  -d '{"name":"Acme","jurisdiction":"gdpr"}'

curl -s localhost:8000/v1/requests \
  -H 'content-type: application/json' \
  -d '{"tenant_id":"<tenant>","email":"alice@example.com","request_text":"Please delete my account.","audit_at":"2026-10-26T00:00:00Z"}'

curl -s -X POST 'localhost:8000/v1/requests/<request>/run?remediate=true'
curl -s localhost:8000/v1/requests/<request>/attestation
```

## Connector SDK

Connectors are the only components that touch customer systems. Implement the
methods you need:

```python
from erasureproof.connectors.base import BaseConnector

class MyWarehouseConnector(BaseConnector):
    type = "warehouse"

    def discover(self, subject, as_of):
        # return list[ResourceRef] for matching records
        ...

    def remediate(self, ref, action, fields=()):
        # delete/redact/anonymize the record
        ...

    def discover_flows(self, subject, as_of):
        # return list[FlowRef] for active sync/import jobs
        ...

    def discover_backups(self, subject, as_of):
        # return list[BackupRef] for restorable snapshots
        ...
```

Built-in connectors:

| Type | Purpose |
|---|---|
| `sql` | SQLite, Postgres, MySQL and any SQLAlchemy URL |
| `postgres` | Postgres-aware SQL connector |
| `local` | Local object-store directory (exports, attachments, logs) |
| `filesystem` / `workspace` | Directory tree with PDF/OCR/archive/SQLite extraction and redaction |
| `s3` | S3-compatible bucket (`pip install "erasureproof[s3]"`) |
| `control` | JSON control plane for sync jobs and backup restore points |

Connector configs are stored per tenant in the API and are validated before use.
SQL table and column names are allow-listed; values are always bound parameters.

## Policy

Policies live in `policies/*.yaml`:

```yaml
name: GDPR Erasure Policy
jurisdiction: gdpr
defaults:
  PRIMARY_ACCOUNT:
    action: TOMBSTONE
    redact_fields: [name, email, phone, email_hash]
    retain_fields: [user_id]
rules:
  - name: legal-hold-retained
    priority: 100
    when: {payload.legal_hold: true}
    action: RETAIN
```

Actions:

| Action | Effect |
|---|---|
| `DELETE` | Remove the whole record |
| `REDACT` | Keep the record, remove required direct identifiers |
| `ANONYMIZE` | Keep the record, irreversibly unlink it from the subject |
| `RETAIN` | Keep the record (legal hold, audit, statutory retention) |
| `TOMBSTONE` | Keep the stable subject reference, remove direct identifiers |

## Evidence intelligence

The `intelligence` package is intentionally local and deterministic:

| Input | What is extracted |
|---|---|
| Text, JSON, CSV, HTML, XML, logs | Full text plus bounded context snippets |
| PDF | Embedded text; page OCR fallback via `pdftoppm` + `tesseract` |
| Images | OCR text and EXIF metadata (GPS fields are not copied into findings) |
| DOCX/XLSX/PPTX | Office XML text, comments and document metadata |
| ZIP/TAR/GZ | Bounded member extraction, recursion depth and size caps |
| SQLite | Table names, schema and text columns, bounded row sampling |
| Unknown binaries | Printable strings fallback, marked low confidence |

Matches are mapped to normalized emails, phones, email hashes, handles, URLs,
IPs and other identifiers. Output is masked by default; raw evidence stays in the
content-addressed store and is referenced by `evidence_id`. Scanned trees are
read-only and symlinks are never followed.

`scan` writes evidence under `.erasureproof/evidence/`, enforces a file limit,
and never writes into the scanned directory. OCR requires `tesseract` and
`pdftoppm` on `PATH`; PDF text extraction works without them.

## Authorized exposure discovery

Exposure checks are **off by default** and require explicit per-scan approval.
They are passive: ErasureProof reads public sources, never bypasses
authentication, never exploits a target and never downloads breach dumps.

```bash
export ERASUREPROOF_EXPOSURE_ENABLED=true
.venv/bin/erasureproof exposure \
  --email alice@example.com \
  --url https://example.com/team \
  --authorized
```

Collectors:

| Collector | What it checks |
|---|---|
| `direct` | Operator-supplied public URLs |
| `wayback` | Internet Archive CDX snapshots for supplied URLs |
| `search` | Serper or Brave search APIs for quoted identifiers |
| `hibp` | Have I Been Pwned breach metadata (no passwords) |
| `github` | GitHub code search using a token |
| `gravatar` | Public Gravatar profile for an email hash |
| `username` | Public GitHub/Keybase account existence |

Guardrails: scheme and credential rejection, private/link-local/loopback DNS
blocking, redirect re-validation, robots.txt enforcement for page fetches,
per-host rate limits, response-size and timeout caps, and collector isolation.
Search and breach collectors require their own API keys and provider terms.
Results are masked in the report and the raw response is stored as evidence.

The `--authorized` flag is an operator assertion, not user authentication. Put
the API behind your own authentication and authorization layer before enabling
exposure scanning, and only check identifiers you are entitled to investigate.

## Step graph

The planner emits a safe order; the graph proves and visualises it. Findings are
roots, flow/restore controls precede record changes, downstream copies precede
primary accounts, and each verification depends on the action that produced its
state.

```bash
curl -s localhost:8000/v1/requests/<request>/graph
curl -s 'localhost:8000/v1/requests/<request>/graph?format=mermaid'
curl -s 'localhost:8000/v1/requests/<request>/graph?format=dot'
```

The API `run` response, attestation payload and `demo --graph` include the same
DAG. Nodes carry phase, operation, state, system/resource and dependencies.

## Approvals, audit and backup

When `ERASUREPROOF_REQUIRE_REMEDIATION_APPROVAL=true`, a request creator cannot
run destructive remediation until a **different administrator** approves it.
Approvals are single-use, expire after `ERASUREPROOF_APPROVAL_TTL_HOURS`, and are
consumed atomically before the run. Audit-only runs (`?remediate=false`) do not
require approval.

Administrative events (request creation, runs, approvals, tenant and connector
changes, exposure scans) are written to `audit_events` and exposed as
tenant-scoped JSON and CSV:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  'localhost:8000/v1/audit-events?limit=100'
curl -H "Authorization: Bearer $TOKEN" \
  -o audit.csv 'localhost:8000/v1/audit-events/export'
```

Create and verify a signed backup archive:

```bash
.venv/bin/erasureproof backup create --output /secure/backups/erasureproof.zip
.venv/bin/erasureproof backup verify /secure/backups/erasureproof.zip
```

The archive contains evidence objects, the ledger, attestations, and a SQLite
snapshot when the metadata store is SQLite. It is signed with the attestation
key; a wrong key or modified member fails verification. Back up PostgreSQL
separately with your provider's tooling. Restoring refuses to overwrite live
data unless `--force` is supplied and the destination is outside the live data
directories.

## Evidence, ledger and attestations

- **Evidence store** (`evidence/store.py`) writes immutable snapshots under
  their SHA-256. Identical content is stored once.
- **Ledger** (`evidence/ledger.py`) is append-only JSONL where each entry commits
  to the previous hash. `erasureproof ledger verify` detects edits, deletions and
  reordering.
- **Attestation** (`core/attestation.py`) is a canonical JSON document containing
  the status, ordered plan, verification results and ledger head, signed with
  HMAC-SHA256. Replace `ERASUREPROOF_ATTESTATION_KEY` with a KMS/Vault-backed
  signer in production.

## Configuration

Copy `.env.example` to `.env` and adjust:

```text
ERASUREPROOF_DATABASE_URL=sqlite:///./.erasureproof/erasureproof.db
ERASUREPROOF_DATA_DIR=./.erasureproof
ERASUREPROOF_WEB_DIR=./web/dist
ERASUREPROOF_DEMO_ENABLED=true
ERASUREPROOF_SELF_SERVE_ENABLED=false
ERASUREPROOF_SANDBOX_TTL_HOURS=168
ERASUREPROOF_ATTESTATION_KEY=change-me
ERASUREPROOF_POLICY_DIR=./policies
ERASUREPROOF_DEFAULT_JURISDICTION=gdpr

# Production access control. Production refuses auth_mode=disabled.
ERASUREPROOF_AUTH_MODE=disabled
# ERASUREPROOF_API_KEYS=[{"key":"...","role":"admin","tenant_id":"*","subject":"admin"}]
# ERASUREPROOF_OIDC_ISSUER=https://idp.example.com
# ERASUREPROOF_OIDC_AUDIENCE=erasureproof
# ERASUREPROOF_OIDC_JWKS_URL=https://idp.example.com/.well-known/jwks.json
ERASUREPROOF_REQUIRE_REMEDIATION_APPROVAL=false
ERASUREPROOF_APPROVAL_TTL_HOURS=24

# Edge and observability. Put TLS and rate limits at the gateway too.
ERASUREPROOF_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
ERASUREPROOF_RATE_LIMIT_PER_MINUTE=0
ERASUREPROOF_HSTS_SECONDS=0
# ERASUREPROOF_METRICS_TOKEN=

# Passive exposure discovery is opt-in. Keep the API key values in a secret store.
ERASUREPROOF_EXPOSURE_ENABLED=false
# ERASUREPROOF_SERPER_API_KEY=
# ERASUREPROOF_BRAVE_API_KEY=
# ERASUREPROOF_GITHUB_TOKEN=
# ERASUREPROOF_HIBP_API_KEY=
```

SQLite is the default so the demo needs no external services. Set a
`postgresql+psycopg://` URL and install the `postgres` extra for production.

## Development

```bash
make check   # ruff + pytest + console typecheck/build
```

The test suite covers intent classification, identity resolution, policy
decisions, DAG ordering, evidence extraction (text/JSON/PDF/ZIP), workspace
scanning, filesystem redaction, exposure authorization/scoring with fake HTTP,
SQL/object-store remediation, ledger tamper detection, attestation signature
verification, the API and the full demo. OCR tests are skipped when host OCR
tools are unavailable.

## Web console

The console reads the same REST API as the CLI.

<p align="center">
  <a href="https://github.com/dsk-dev-ai/erasureproof/blob/main/docs/assets/dashboard.png">
    <img src="https://raw.githubusercontent.com/dsk-dev-ai/erasureproof/main/docs/assets/dashboard.png" alt="ErasureProof operations dashboard with audit metrics, findings, status mix, recent audits, control coverage, policies, and ledger state" width="100%">
  </a>
</p>

<p align="center"><sub>Overview: proven findings, verification rate, attestation coverage, risk, evidence, and the live ledger. <a href="https://github.com/dsk-dev-ai/erasureproof/blob/main/docs/assets/dashboard.png">Open full size</a>.</sub></p>

It contains:

| View | Purpose |
|---|---|
| Landing | Product overview and one-click demo bootstrap. |
| Overview | Status mix, audit trend, verification rate, risk, recent audits, and live ledger. |
| Requests | Search, filters, intent state, and audit cutoff. |
| Request detail | Findings, remediation plan, dependency graph, evidence, verification, and signed attestation. |
| Subjects | Current and historical identifiers resolved into stable subjects. |
| Connectors | Source inventory and connection configuration. |
| Exposure | Authorized passive scan of public sources with safety guardrails. |
| Evidence & ledger | Artifact integrity checks, hash-chain verification, and the policy matrix. |
| Settings | Theme, workspace, bearer token, audit export, runtime, and environment configuration. |
| API keys | Create, rotate, revoke, and audit tenant-scoped keys. |
| Docs | Product, architecture, API, deployment, and security documentation. |

Animation is implemented with Framer Motion, charts with Recharts, and server
state with TanStack Query. The UI respects `prefers-reduced-motion` and includes
a keyboard command palette (`Cmd/Ctrl+K`).

## Changelog

See [`CHANGELOG.md`](CHANGELOG.md) for release history.

## Design decisions

- **Evidence before action.** Discovery snapshots are written before remediation,
  so the finding is reproducible even after the record is gone.
- **Planner is deterministic.** Phase order is fixed; resources are ordered by
  dependency rank, then system ID and resource ID.
- **Connectors are narrow.** They expose discovery, remediation and flow/restore
  control — no policy or identity logic — which keeps customer credentials and
  data-access code isolated.
- **In-process by default.** Temporal is optional; the orchestrator is a plain
  function so it can be scheduled by any durable workflow engine.
- **No silent trust.** Verification re-reads state instead of trusting delete
  return codes, and attestations commit to the verification results.

## Roadmap

- Durable Temporal workflows backed by the approval ledger
- Residency-aware multi-region connectors and retention calendars
- Per-connector OAuth/KMS credential management
- Continuous resurrection monitoring (alert when deleted data reappears)
- Scheduled exposure rescans with diffing and archive/cache takedown tracking
- Attestation transparency log and third-party verifier CLI
- Policy simulation and dry-run impact reports

## Kubernetes

Production manifests live in [`deploy/kubernetes`](deploy/kubernetes). They run
two or more replicas against managed PostgreSQL and a shared `ReadWriteMany`
volume, enable API-key authentication, require remediation approval, add
probes, HPA, ingress TLS, and a default-deny network policy. See the deployment
README before applying.

## Security

Never commit credentials. Connector secrets should come from a secret manager or
environment variables. In production, startup validation rejects disabled
authentication and the default attestation key. Use one API key per operator,
scope keys to a tenant, keep a wildcard admin key offline, and scrape `/metrics`
with a dedicated token. See [SECURITY.md](SECURITY.md) for reporting guidance
and [`deploy/kubernetes`](deploy/kubernetes) for hardening notes.

## Release verification

[`v1.1.2`](https://github.com/dsk-dev-ai/erasureproof/releases/tag/v1.1.2) is
the current stable release. It hardens deletion-status decisions, evidence
isolation, path handling, and cross-process mutation safety. The release gate
is:

```bash
make check                 # ruff, pytest, console typecheck and production build
make package-check         # both sdists/wheels plus twine metadata
docker build -t erasureproof .
docker run --rm -p 18000:8000 erasureproof
curl -fsS localhost:18000/healthz
```

CI runs lint, the full test suite, package metadata checks, and the production
console build on every push, pull request, and release tag. The hosted
deployment is smoke-tested for health, readiness, sandbox creation, audit
execution, attestation verification, and ledger integrity. See
[CHANGELOG.md](CHANGELOG.md) for the release history and
[docs/RELEASE.md](https://github.com/dsk-dev-ai/erasureproof/blob/main/docs/RELEASE.md)
for the release evidence.

## Sponsor ErasureProof

If ErasureProof saves you time, you can support continued development through
[GitHub Sponsors](https://github.com/sponsors/dsk-dev-ai). Sponsorship funds
connector coverage, regression tests, and hosted demo infrastructure.

<p align="center">
  <a href="https://github.com/sponsors/dsk-dev-ai"><img src="https://img.shields.io/badge/Sponsor%20Darshan%20Kachare-%E2%9D%A4-db2777?style=for-the-badge" alt="Sponsor Darshan Kachare on GitHub"></a>
</p>

## License

Apache-2.0. See [LICENSE](https://github.com/dsk-dev-ai/erasureproof/blob/main/LICENSE).
