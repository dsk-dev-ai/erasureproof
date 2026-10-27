# API reference

Base URL: `http://localhost:8000`

Interactive OpenAPI: `GET /docs`

## Authentication

When `ERASUREPROOF_AUTH_MODE` is `api_key` or `oidc`, send a bearer token or API
key on every `/v1` request:

~~~bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/v1/tenants
# API keys can also use:
curl -H "X-API-Key: $KEY" http://localhost:8000/v1/tenants
~~~

Roles: `viewer` can read, `operator` can create requests and run audits, and
`admin` can manage tenants/connectors, decide approvals, and export audit events.
Tenant-scoped principals receive `404` outside their tenant.

## Health

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/healthz` | Liveness status, version, database type. |
| `GET` | `/livez` | Process liveness for Kubernetes. |
| `GET` | `/readyz` | Database, schema, storage, ledger, policy, and config checks. |
| `GET` | `/metrics` | Prometheus exposition; token or admin auth. |
| `GET` | `/version` | Product name and version. |

## Workspaces and subjects

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/tenants` | List visible workspaces. |
| `POST` | `/v1/tenants` | Create a workspace (wildcard admin). |
| `GET` | `/v1/tenants/{id}/subjects` | List subjects and identifiers. |
| `POST` | `/v1/subjects` | Create a subject (operator). |
| `GET` | `/v1/overview?tenant_id=…` | Console metrics and recent activity. |
| `GET` | `/v1/policies` | Policy matrix. |
| `GET` | `/v1/ledger` | Tenant-scoped ledger entries and head. |
| `POST` | `/v1/ledger/verify` | Verify the full hash chain. |

## Requests

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/requests` | List requests. |
| `POST` | `/v1/requests` | Create a request (operator). |
| `GET` | `/v1/requests/{id}` | Request, plan, result, and approval state. |
| `POST` | `/v1/requests/{id}/run?remediate=true&force=false` | Run the audit. |
| `GET` | `/v1/requests/{id}/graph` | Step DAG and critical path. |
| `GET` | `/v1/requests/{id}/attestation` | Signed attestation. |

Example:

~~~bash
curl -X POST http://localhost:8000/v1/requests \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "tenant_id": "ten_demo",
    "email": "alice@example.com",
    "request_text": "Please delete my account and all of my personal data.",
    "audit_at": "2026-10-20T12:00:00Z",
    "jurisdiction": "gdpr"
  }'
~~~

A destructive run returns `428` when approval is required and no active approval
exists. Use `?remediate=false` for an audit-only run.

## Approvals

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/v1/requests/{id}/approval` | Approve or reject remediation (admin). |
| `GET` | `/v1/requests/{id}/approvals` | Approval history (viewer). |
| `GET` | `/v1/approvals/active` | Active approvals in scope. |

~~~bash
curl -X POST http://localhost:8000/v1/requests/$REQUEST/approval \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"decision":"APPROVED","reason":"reviewed by second administrator"}'
~~~

Approval is single-use and expires after `ERASUREPROOF_APPROVAL_TTL_HOURS`.
Under separation of duties, the administrator who created the request cannot
approve it.

## Audit events

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/audit-events?limit=100` | Administrative events (admin). |
| `GET` | `/v1/audit-events/export` | Tenant-scoped CSV export (admin). |

## Evidence

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/evidence` | List evidence metadata in tenant scope. |
| `GET` | `/v1/evidence/{id}` | Evidence metadata. |
| `GET` | `/v1/evidence/{id}/content` | Authenticated artifact bytes. |
| `POST` | `/v1/evidence/{id}/verify` | Verify SHA-256 fingerprint. |

## Exposure

`POST /v1/exposure/scan`

Requires `authorized: true` in the body and `ERASUREPROOF_EXPOSURE_ENABLED=true` on the server.

## Demo

`POST /v1/demo/seed` creates the non-destructive demo workspace when demo mode is enabled. Requires an operator and only targets `ten_demo`.

## Backup CLI

~~~bash
erasureproof backup create --output /secure/backups/erasureproof.zip
erasureproof backup verify /secure/backups/erasureproof.zip
erasureproof backup restore /secure/backups/erasureproof.zip --force
~~~

Archives are signed with `ERASUREPROOF_ATTESTATION_KEY`; verification fails on a
wrong key or modified member. PostgreSQL must be backed up separately.
