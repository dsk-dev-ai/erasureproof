# ErasureProof

**Proof-of-erasure for every copy of personal data.**

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

The `1.0` line turns the engine into a production control plane:

- **Authentication and tenant isolation** with static API keys or OIDC, viewer /
  operator / administrator roles, and server-side tenant scoping on every read
  and write.
- **Approval-gated remediation** where a second administrator authorizes a
  single-use, time-limited destructive run and every decision is audited.
- **A tamper-evident operational audit trail** with tenant-scoped CSV export,
  plus signed backups of evidence, the ledger, attestations, and metadata.
- **A hardened edge** with request IDs, per-IP rate limiting, Prometheus metrics,
  security headers, configurable CORS, production configuration validation,
  readiness probes, and Kubernetes manifests.
- **A full console** for overview metrics, request audits, identity graphs,
  remediation plans, evidence inspection, ledger verification, policy review,
  and demo discovery.
- **Evidence intelligence** for PDFs, images, OCR, Office files, archives,
  SQLite snapshots, metadata and free text, with subject matching over current
  and historical identifiers.
- **Authorized exposure discovery** for public URLs, web archives, search APIs,
  breach metadata and public profiles — passive checks only, disabled by default.
- **A step dependency graph** that makes remediation ordering inspectable and
  renderable as Mermaid, Graphviz DOT or JSON, or interactively in the console.

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

## Quickstart

Requirements: Python 3.10+ (3.11/3.12 recommended) and `uv` or `pip`.

```bash
# with uv (recommended)
uv venv .venv
uv pip install --python .venv/bin/python -e ".[dev]"

# or with a standard virtualenv
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

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
policy configuration, and built-in product documentation.

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

The Vite build requires Node 20 or newer and uses `/console/` as its production
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

The public deployment runs the console at `/console`, OpenAPI at `/docs`, and the
API under `/v1`. Create a free isolated sandbox with a one-time API key:

```bash
curl -s -X POST "$BASE_URL/v1/onboarding/sandbox" \
  -H 'content-type: application/json' \
  -d '{"workspace_name":"Acme privacy"}'
```

Use the returned key with the Python SDK:

```python
from erasureproof_sdk import create_sandbox

client, sandbox = create_sandbox("https://your-host")
run = client.run_request(sandbox["sample_request_id"], remediate=False)
print(run["status"], run["attestation"]["signature"])
```

See [`docs/API.md`](docs/API.md) for endpoint, role, approval, and error
reference, and [`docs/DEPLOY_RENDER.md`](docs/DEPLOY_RENDER.md) for the Render
deployment profile.

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
| `s3` | S3-compatible bucket (`pip install -e ".[s3]"`) |
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

The console reads the same REST API as the CLI. It contains:

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

## License

Apache-2.0. See [LICENSE](LICENSE).
