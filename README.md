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
   restore points. Each snapshot is written to a content-addressed evidence
   store.
4. **Policy.** A YAML policy maps each category to `DELETE`, `REDACT`,
   `ANONYMIZE`, `RETAIN` or `TOMBSTONE`. Legal holds and retention obligations
   override erasure.
5. **Planning.** Findings cite evidence. Remediation disables flows and blocks
   restores first, then removes downstream copies before their source records.
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
.venv/bin/erasureproof ledger verify
.venv/bin/erasureproof attestation verify .erasureproof/attestations/<request_id>.attestation.json
```

### Run the API

```bash
.venv/bin/erasureproof serve --reload
# OpenAPI docs: http://localhost:8000/docs
```

### Run with Docker

```bash
docker compose up --build
# API:   http://localhost:8000
# Docs:  http://localhost:8000/docs
# Postgres is provisioned automatically.
```

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
ERASUREPROOF_ATTESTATION_KEY=change-me
ERASUREPROOF_POLICY_DIR=./policies
ERASUREPROOF_DEFAULT_JURISDICTION=gdpr
```

SQLite is the default so the demo needs no external services. Set a
`postgresql+psycopg://` URL and install the `postgres` extra for production.

## Development

```bash
.venv/bin/pytest
.venv/bin/ruff check .
```

The test suite covers intent classification, identity resolution, policy
decisions, plan ordering, SQL/object-store remediation, ledger tamper
detection, attestation signature verification, the API and the full demo.

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

- Durable Temporal workflows with human approval gates
- Residency-aware multi-region connectors and retention calendars
- Per-connector OAuth/KMS credential management
- Continuous resurrection monitoring (alert when deleted data reappears)
- Attestation transparency log and third-party verifier CLI
- Policy simulation and dry-run impact reports

## Security

Never commit credentials. Connector secrets should come from a secret manager or
environment variables. See [SECURITY.md](SECURITY.md) for reporting guidance.

## License

Apache-2.0. See [LICENSE](LICENSE).
