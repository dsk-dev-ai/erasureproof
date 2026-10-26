# API reference

Base URL: `http://localhost:8000`

Interactive OpenAPI: `GET /docs`

## Health

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/healthz` | Status, version, database type. |
| `GET` | `/version` | Product name and version. |

## Workspaces and subjects

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/tenants` | List workspaces. |
| `POST` | `/v1/tenants` | Create a workspace. |
| `GET` | `/v1/tenants/{id}/subjects` | List subjects and identifiers. |
| `GET` | `/v1/overview?tenant_id=…` | Console metrics and recent activity. |

## Requests

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/requests` | List requests. |
| `POST` | `/v1/requests` | Create a request. |
| `GET` | `/v1/requests/{id}` | Request, plan, and stored result. |
| `POST` | `/v1/requests/{id}/run?remediate=true&force=false` | Run the audit. |
| `GET` | `/v1/requests/{id}/graph` | Step DAG and critical path. |

Example:

~~~bash
curl -X POST http://localhost:8000/v1/requests \
  -H 'Content-Type: application/json' \
  -d '{
    "tenant_id": "ten_demo",
    "email": "alice@example.com",
    "request_text": "Please delete my account and all of my personal data.",
    "audit_at": "2026-10-20T12:00:00Z",
    "jurisdiction": "gdpr"
  }'
~~~

## Evidence and ledger

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/evidence` | List evidence metadata. |
| `GET` | `/v1/evidence/{id}/content` | Download artifact bytes. |
| `POST` | `/v1/evidence/{id}/verify` | Verify SHA-256 fingerprint. |
| `GET` | `/v1/ledger` | Read ledger entries and head. |
| `POST` | `/v1/ledger/verify` | Verify the full chain. |

## Exposure

`POST /v1/exposure/scan`

Requires `authorized: true` in the body and `ERASUREPROOF_EXPOSURE_ENABLED=true` on the server.

## Demo

`POST /v1/demo/seed` creates the non-destructive demo workspace when demo mode is enabled.
