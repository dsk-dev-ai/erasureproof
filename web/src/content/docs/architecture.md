# Architecture

ErasureProof is organized as a set of explicit, testable stages. Each stage produces data the next stage can verify.

~~~text
Request
  │
  ├─► Intent classifier
  │
  ├─► Identity graph (current + historical identifiers)
  │
  ├─► Connector fan-out (read-only discovery)
  │
  ├─► Policy engine
  │
  ├─► Findings + ordered remediation plan
  │
  ├─► Flow/restore controls + record remediation
  │
  ├─► Re-discovery + verification
  │
  └─► Signed attestation + hash-chained ledger
~~~

## Core modules

| Area | Responsibility |
|---|---|
| `core/identity.py` | Resolve current and historic identifiers into a stable subject. |
| `core/normalize.py` | Classify request intent and normalize identifiers. |
| `core/policy.py` | Decide `DELETE`, `REDACT`, `ANONYMIZE`, `RETAIN`, or `TOMBSTONE`. |
| `connectors/` | Discover resources in SQL, filesystem, object storage, and control systems. |
| `intelligence/` | Extract text, OCR, metadata, archives, and SQLite snapshots. |
| `orchestrator/` | Build findings, execute remediation, re-discover, and verify. |
| `core/graph.py` | Validate dependency order and expose the step DAG. |
| `evidence/` | Content-addressed artifacts, ledger, and signed attestations. |
| `exposure/` | Passive public-source collection with authorization guardrails. |
| `api/` | FastAPI REST surface used by the CLI and web console. |

## Determinism

Given the same subject, policy, connector state, and audit cutoff, the engine aims to produce the same plan ordering and serialization. Sorts are explicit, identifiers are normalized, and graph traversal uses stable step numbers.

## Storage

SQLite is the default metadata store. PostgreSQL is supported through `ERASUREPROOF_DATABASE_URL`. Binary evidence lives on local disk under a content-addressed layout:

~~~text
.erasureproof/
├── objects/<sha-prefix>/<sha256>
├── meta/<evidence_id>.json
├── ledger.jsonl
└── attestations/<request_id>.attestation.json
~~~

## API request lifecycle

1. `POST /v1/requests` creates a request. Non-deletion intent is immediately `NOT_APPLICABLE`.
2. `POST /v1/requests/{id}/run` resolves identity, discovers, plans, remediates, verifies, and signs.
3. `GET /v1/requests/{id}` returns the stored request, plan, and result.
4. `GET /v1/requests/{id}/graph` returns nodes, edges, cycle state, and critical path.
5. `GET /v1/ledger` and `POST /v1/ledger/verify` expose the audit chain.
