# Architecture

## Goals

1. Determine whether a request actually authorizes deletion.
2. Reconstruct the full subject identity, including historical identifiers.
3. Find every relevant copy of their data at a specific `audit_at` time.
4. Apply your policy to each category, including retention and tombstone rules.
5. Remediate in a safe order: stop recreation paths, then remove dependent copies,
   then sources.
6. Prove the final state with evidence and a signed attestation.
7. Keep the audit trail append-only and independently verifiable.

Non-goals: being a data catalog, a backup product, a consent-management platform,
or a general workflow engine. ErasureProof integrates with those systems.

## Components

```text
┌─────────────────────── Web console / API / CLI / Scheduler ────────────────────┐
│                                                                              │
│  Request intake ──► Intent classifier ──► Identity resolver                  │
│                                                │                             │
│                                                ▼                             │
│                                     Orchestrator (runner)                    │
│                    ┌───────────────┬───────────┴───────────┬─────────────┐    │
│                    ▼               ▼                       ▼             ▼    │
│               Connector A     Connector B             Policy engine   Planner │
│              (SQL, S3, …)    (control plane)                 │             │    │
│                    │               │                       │             │    │
│                    └───────┬───────┴───────────────────────┘             │    │
│                            ▼                                             │    │
│                    Evidence store (content-addressed)                    │    │
│                            │                                             │    │
│                            ▼                                             │    │
│                    Re-discovery ──► Verifier ──► Attestation service         │
│                                                        │                     │
│                                                        ▼                     │
│                                              Hash-chained ledger             │
└──────────────────────────────────────────────────────────────────────────────┘
```

| Component | Responsibility |
|---|---|
| `core/normalize.py` | Conservative, multilingual intent classification |
| `core/identity.py` | Reunite current and historical identifiers into a subject graph |
| `connectors/base.py` | SDK contract and evidence helper |
| `connectors/sql.py` | Relational discovery and remediation |
| `connectors/s3.py` | Object-store discovery and content redaction |
| `connectors/control.py` | Sync-job and backup restore control plane |
| `core/policy.py` | YAML policy loading, rule matching, compliance checks |
| `core/planner.py` | Findings, ordered remediation, verification plan |
| `core/verifier.py` | Re-read state and check expected outcomes |
| `core/attestation.py` | Canonical payload, HMAC signature, file issuance |
| `evidence/store.py` | Immutable snapshots under SHA-256 |
| `evidence/ledger.py` | Append-only JSONL hash chain |
| `orchestrator/runner.py` | The end-to-end run loop |
| `web/` | Vite + React operations console served by FastAPI at `/console` |

## Request lifecycle

```text
PENDING ──► audit ──► COMPLETE
   │            │
   │            └──► INCOMPLETE ──► remediation ──► re-audit ──► COMPLETE
   │                                                        └──► INCOMPLETE
   └──► NOT_APPLICABLE (intent is not deletion)
```

`audit_at` is the cutoff. Connectors must ignore records, flows and backups that
only became visible after that time. The planner treats workflow statuses as
claims; only discovered state and evidence count.

## Web console

The console is a separate Vite + React + TypeScript application in `web/`. It
uses TanStack Query for server state, React Router for client routes, Framer
Motion for transitions, Recharts for overview charts and Tailwind for the design
system. It has no server-rendering tier and calls the same `/v1` API as the CLI.

```text
Browser ──► FastAPI
              ├── /v1/*       JSON API
              ├── /healthz    liveness
              └── /console/*  static assets + SPA fallback
```

A production build uses `/console/` as Vite's base. FastAPI serves hashed assets
with immutable caching and returns `index.html` for unknown client routes. The
console can be built independently (`make web-build`) and is copied into the
Docker image in a multi-stage build. When `web/dist` is absent, API routes and
OpenAPI docs remain available and the console route reports that it is not built.

## Data model

| Table | Purpose |
|---|---|
| `tenants` | Customer boundary and default jurisdiction |
| `subjects` | Stable `user_id` per tenant |
| `identifiers` | Email, phone and email hash history with validity windows |
| `connectors` | Encrypted connector config and system binding |
| `requests` | Request text, timestamps, status, plan and result |
| `evidence` | Metadata for content-addressed snapshots |
| `attestations` | Issued signature, path, status and payload |

`identifiers.normalized` is indexed so a request email can be matched to current
or historical forms. Email hashes are derived for every email, not just the
request address.

## Planning order

1. **Findings** — remaining records, exposed identifiers, active flows, restore
   risks. Each finding cites an evidence ID.
2. **Remediation** — disable flows, block restores, then process resources by
   dependency rank: exports/search/analytics/logs/support/replicas/archives before
   primary accounts and tombstones. Within a rank, sort by system ID and resource
   ID for deterministic output.
3. **Verification** — one or more checks per remediated resource plus retained
   records. Before remediation these are proposed checks with no evidence ID; in
   a complete case they cite the evidence that proves the state.

## Policy semantics

- `DELETE` removes the whole record.
- `REDACT` removes the configured direct identifiers but keeps the record.
- `ANONYMIZE` replaces identifiers with irreversible tokens.
- `RETAIN` keeps the record, typically for legal hold, audit or statutory
  retention.
- `TOMBSTONE` keeps the stable subject reference (`user_id`) and removes direct
  identifiers.

Precedence: explicit legal hold → `retention_required` → highest-priority matching
rule → category default. Unknown categories fall back to `DELETE` so the engine
fails closed on erasure.

## Evidence and attestation

Evidence files are stored under `objects/<sha[:2]>/<sha>` with metadata in
`meta/<evidence_id>.json`. Identical content is stored once. Evidence is written
before remediation, so a finding remains reproducible after the record is gone.

The ledger entry hash commits to `{seq, timestamp, event, request_id, payload,
prev_hash}`. Any edit, deletion or reordering breaks the chain.

An attestation payload contains:

- attestation version, request ID, status, issue time and ledger head;
- summary counts and verification pass/fail state;
- the full ordered plan;
- verification results.

The signature is `HMAC-SHA256(key, canonical_json(payload))` with sorted keys and
compact separators. Verification recomputes the MAC and compares in constant time.

## Failure semantics

- Connector discovery failures are recorded on the run result and in the ledger;
  other connectors continue. A partial inventory must not masquerade as proof, so
  the attestation carries the error list.
- Remediation failures do not abort the run; verification catches the unmet state
  and the final status stays `INCOMPLETE`.
- A redacted record may no longer match on the erased email. SQL connectors
  therefore also match on the stable `user_id`, and verification uses the
  connector's key-based check rather than re-discovery alone.
- Flows and backups are re-read after controls are applied, so the verifier sees
  `DISABLED`/`BLOCKED` rather than trusting the action response.

## Threat model

| Threat | Mitigation |
|---|---|
| Connector lies about deletion | Re-read state during verification |
| Evidence altered after the fact | Content-addressed store + hash-chained ledger |
| Attestation forged or edited | HMAC over canonical payload; KMS signer in production |
| Deleting data under legal hold | Policy precedence and per-record decisions |
| Deleting the source before a replica | Dependency-ranked remediation |
| Re-creation by sync/restore | Flow/restore findings and pre-record controls |
| Scope misses old identifiers | Historical identifier graph and email hashes |
| Post-audit evidence changes the answer | `as_of` filtering in discovery |

## Scaling path

- Replace the in-process runner with Temporal workflows; the runner is already a
  pure function over connectors, policy, evidence and ledger.
- Shard discovery by connector and cache snapshots; evidence IDs are stable.
- Move the ledger to an append-only store (S3 Object Lock, immutability windows)
  while keeping the same hash-chain format.
- Add per-connector rate limits, retries and circuit breakers.
- Store connector credentials in a KMS/Vault-backed secret provider.
- Add authentication, per-tenant authorization and audit of API access.

## Known limitations

- The reference API is unauthenticated and intended for local/controlled use.
- Only local HMAC signing ships by default; production should use asymmetric
  signing or a managed key.
- There is no built-in continuous resurrection monitor yet; the roadmap includes
  scheduled re-audits and alerts.
- Connector coverage is intentionally small: SQL, S3-compatible object stores and
  a JSON control plane. The SDK is the extension point.
