# ErasureProof API

The ErasureProof API turns a deletion request into an evidence-backed audit, an
ordered remediation plan, verification checks, and a signed attestation. Every
route is tenant-scoped. The OpenAPI document is served at `/docs` and
`/openapi.json`.

- Base URL: your deployment origin, for example `https://erasureproof.onrender.com`
- Content type: `application/json`
- Authentication: `Authorization: Bearer <key>` or `X-API-Key: <key>`
- Versioning: routes are under `/v1`

## Get a sandbox key

`POST /v1/onboarding/sandbox` is public when self-service onboarding is enabled.
It creates an isolated tenant with fictional seeded data, three connectors, and
one ready-to-run request. The returned administrator key is shown once and is
scoped to that tenant.

```bash
curl -s -X POST "$BASE_URL/v1/onboarding/sandbox" \
  -H 'content-type: application/json' \
  -d '{"workspace_name":"Acme privacy","jurisdiction":"gdpr"}'
```

```json
{
  "tenant_id": "ten_...",
  "tenant_name": "Acme privacy (sandbox)",
  "api_key": "ep_live_...",
  "key_id": "key_...",
  "key_prefix": "ep_live_...",
  "role": "admin",
  "expires_at": "2026-11-04T12:00:00Z",
  "sample_request_id": "req_...",
  "sample_email": "alice@example.com",
  "quickstart": {"docs": "/docs", "console": "/console", "run_audit": "..."}
}
```

The key is stored as a SHA-256 hash. ErasureProof cannot show it again.

## Run the seeded audit

```bash
curl -s -X POST "$BASE_URL/v1/requests/$REQUEST_ID/run?remediate=false" \
  -H "Authorization: Bearer $ERASUREPROOF_API_KEY"
```

`remediate=false` is a read-only audit. `remediate=true` executes the ordered
plan and is approval-gated when `ERASUREPROOF_REQUIRE_REMEDIATION_APPROVAL=true`.
Terminal requests are cached; add `force=true` to run again.

The response contains:

| Field | Meaning |
|---|---|
| `status` | `COMPLETE`, `INCOMPLETE`, `NOT_APPLICABLE`, or `PENDING` |
| `plan.steps` | Findings, remediation, and verification in dependency order |
| `graph` | The same steps as a DAG with dependencies |
| `verification` | Re-discovered checks and whether each passed |
| `actions` | Actions actually executed during remediation |
| `attestation` | Signature, ledger head, and canonical payload |
| `errors` | Connector or remediation errors that affected the result |

A `COMPLETE` result means every relevant copy has the required treatment,
policy-required retained records remain, and no active flow or restore path can
recreate prohibited data. A workflow's own status claim is never trusted.

## Retrieve the proof

```bash
curl -s "$BASE_URL/v1/requests/$REQUEST_ID/attestation" \
  -H "Authorization: Bearer $ERASUREPROOF_API_KEY"
```

The attestation payload is canonical JSON signed with HMAC-SHA256 and committed
to a SHA-256 hash-chained ledger. Verify ledger integrity with
`POST /v1/ledger/verify` or from the CLI with `erasureproof attestation verify`.

## Create your own request

First resolve current and historical identifiers, register connectors, then
submit the request:

```bash
curl -s -X POST "$BASE_URL/v1/requests" \
  -H "Authorization: Bearer $ERASUREPROOF_API_KEY" \
  -H 'content-type: application/json' \
  -d '{
    "tenant_id": "ten_...",
    "email": "alice@example.com",
    "request_text": "Please delete my account and all personal data.",
    "audit_at": "2026-10-28T00:00:00Z",
    "jurisdiction": "gdpr"
  }'
```

Only an explicit, non-negated deletion request authorizes deletion. Access,
correction, export, marketing opt-out, and restriction requests return
`NOT_APPLICABLE` with an empty plan.

Connector types are listed at `GET /v1/connector-types`. Typical setup:

```bash
curl -s -X POST "$BASE_URL/v1/connectors" \
  -H "Authorization: Bearer $ERASUREPROOF_API_KEY" \
  -H 'content-type: application/json' \
  -d '{
    "tenant_id": "ten_...",
    "type": "postgres",
    "name": "account-service",
    "config": {
      "system_id": "account_service",
      "url": "postgresql+psycopg://readonly:...@host/db",
      "tables": {
        "customers": {
          "category": "PRIMARY_ACCOUNT",
          "pk": "customer_id",
          "user_id_column": "user_id",
          "subject_columns": [["email", "EMAIL"]],
          "pii_fields": ["name", "email", "phone", "email_hash"]
        }
      }
    }
  }'
```

Use a read-only database credential for discovery. Remediation requires write
access and should be a separate, least-privileged credential. Secrets belong in a
secret manager or a server-side environment, never in browser code.

## API keys and roles

| Role | Capabilities |
|---|---|
| `viewer` | Read requests, subjects, evidence, ledger, overview, and attestations |
| `operator` | Viewer plus create requests, run audits, and run approved remediation |
| `admin` | Operator plus tenants, connectors, API keys, and approvals |

Create a key with a bounded lifetime. The response contains the only plaintext
copy:

```bash
curl -s -X POST "$BASE_URL/v1/api-keys" \
  -H "Authorization: Bearer $ADMIN_KEY" \
  -H 'content-type: application/json' \
  -d '{"tenant_id":"ten_...","name":"CI","role":"operator","expires_in_days":90}'
```

| Route | Purpose |
|---|---|
| `GET /v1/api-keys` | List active keys (prefix only) |
| `POST /v1/api-keys` | Create a key and return plaintext once |
| `POST /v1/api-keys/{id}/rotate` | Issue a replacement and revoke the old key |
| `DELETE /v1/api-keys/{id}` | Revoke immediately |

Expired and revoked keys fail with `401`. Key creation, rotation, and revocation
are written to the tenant audit trail.

## Approvals

When destructive remediation requires approval, an operator creates the request,
then a different admin approves it:

```bash
curl -s -X POST "$BASE_URL/v1/requests/$REQUEST_ID/approval" \
  -H "Authorization: Bearer $ADMIN_KEY" \
  -H 'content-type: application/json' \
  -d '{"decision":"APPROVED","reason":"DPO review complete"}'
```

Approvals are single-use, time-limited, and consumed atomically before the run.
A run without a valid approval returns `428`.

## Operational endpoints

| Route | Purpose |
|---|---|
| `GET /healthz` | Liveness and database check |
| `GET /readyz` | Readiness with schema and schema-version checks |
| `GET /metrics` | Prometheus metrics (token or admin auth) |
| `GET /v1/overview?tenant_id=` | Status mix, verification rate, risk, recent activity |
| `GET /v1/audit-events?tenant_id=` | Tenant-scoped operational audit |
| `GET /v1/audit-events/export` | CSV export |
| `GET /v1/evidence` | Evidence metadata |
| `POST /v1/ledger/verify` | Verify the hash chain |
| `GET /v1/requests/{id}/graph?format=mermaid` | Render the step DAG |

## Errors

| Status | Meaning |
|---|---|
| `400` | Invalid request or missing tenant |
| `401` | Missing, invalid, expired, or revoked credential |
| `403` | Role too low or cross-tenant operation |
| `404` | Resource not found or hidden by tenant scoping |
| `409` | Conflict, key limit, or self-approval |
| `422` | Schema validation failed |
| `428` | Remediation approval required |
| `429` | Rate limit or sandbox quota exceeded |
| `503` | Configuration or dependency unavailable |

Errors return `{"detail": "..."}`. Every response includes `X-Request-ID`; quote
it when reporting a problem. Never include an API key in a support request.

## Rate limits and quotas

The edge limiter returns `429` with `Retry-After` and `X-RateLimit-*` headers.
Sandbox onboarding has a per-IP daily quota and a global daily cap. Configure
these with:

```text
ERASUREPROOF_RATE_LIMIT_PER_MINUTE=300
ERASUREPROOF_SANDBOX_DAILY_LIMIT=100
ERASUREPROOF_SANDBOX_PER_IP_DAILY_LIMIT=3
ERASUREPROOF_SANDBOX_TTL_HOURS=168
```

Public sandbox keys expire. Production tenants should issue their own keys and
use a secret manager. For data-residency or retention commitments, keep the
controlled evidence store on durable storage; the free Render profile is
ephemeral.

## SDKs

- Python: [`sdk/python`](../sdk/python)
- OpenAPI: use `/openapi.json` with any generator for TypeScript, Go, Java, or
  another language.

## Production checklist

1. Use HTTPS and a unique `ERASUREPROOF_ATTESTATION_KEY` from a secret manager.
2. Enable `ERASUREPROOF_AUTH_MODE=api_key` (or OIDC) and disable the default key.
3. Scope operator keys to one tenant; keep wildcard admin keys offline.
4. Set `ERASUREPROOF_REQUIRE_REMEDIATION_APPROVAL=true` for destructive runs.
5. Use a managed PostgreSQL database with backups and point
   `ERASUREPROOF_DATABASE_URL` at it.
6. Use durable storage for evidence, the ledger, and attestations.
7. Set CORS to your console origin and rate limits at the ingress.
8. Scrape `/metrics` with a dedicated token and alert on `429`, `5xx`, and
   failed verification.
