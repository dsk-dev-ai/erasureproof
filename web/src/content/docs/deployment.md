# Deployment

## Local

~~~bash
uv venv .venv
uv pip install --python .venv/bin/python -e ".[dev,oidc]"
.venv/bin/uvicorn erasureproof.main:app --port 8000
~~~

Local development uses `ERASUREPROOF_AUTH_MODE=disabled` and the demo signing
key. Production startup rejects both defaults.

## Docker

The image is multi-stage: the frontend is built with Node, then copied into a
Python runtime that includes OCR, document tooling, PostgreSQL, and OIDC support.

~~~bash
# Local demo, authentication disabled
docker compose up --build

# Hardened single host: external PostgreSQL, API keys, approvals, metrics token
export ERASUREPROOF_DATABASE_URL='postgresql+psycopg://...'
export ERASUREPROOF_ATTESTATION_KEY="$(openssl rand -hex 32)"
export ERASUREPROOF_API_KEYS='[{"key":"...","role":"admin","tenant_id":"*","subject":"admin"}]'
export ERASUREPROOF_METRICS_TOKEN="$(openssl rand -hex 32)"
export ERASUREPROOF_CORS_ORIGINS='https://erasureproof.example.com'
docker compose -f docker-compose.production.yml up -d --build
~~~

Set `ERASUREPROOF_DATA_DIR=/data` when mounting a volume.

## Authentication

Static API keys are the simplest production option:

~~~bash
export ERASUREPROOF_AUTH_MODE=api_key
export ERASUREPROOF_API_KEYS='[
  {"key":"admin-key","role":"admin","tenant_id":"*","subject":"ops-admin"},
  {"key":"tenant-key","role":"operator","tenant_id":"ten_acme","subject":"acme-ops"}
]'
~~~

Roles are `viewer`, `operator`, and `admin`. Tenant-scoped keys receive `404` for
resources outside their tenant. Wildcard (`tenant_id: "*"`) admins can manage all
tenants; keep that key offline for break-glass use.

OIDC validates RS256/384/512 tokens against the issuer, audience, and JWKS URL:

~~~bash
export ERASUREPROOF_AUTH_MODE=oidc
export ERASUREPROOF_OIDC_ISSUER=https://idp.example.com
export ERASUREPROOF_OIDC_AUDIENCE=erasureproof
export ERASUREPROOF_OIDC_JWKS_URL=https://idp.example.com/.well-known/jwks.json
export ERASUREPROOF_OIDC_ROLE_CLAIM=roles
export ERASUREPROOF_OIDC_TENANT_CLAIM=tenant_id
~~~

In the console, use the key button in the top bar or Settings → API access to
store a bearer token for the browser session.

## Approvals

~~~bash
export ERASUREPROOF_REQUIRE_REMEDIATION_APPROVAL=true
export ERASUREPROOF_APPROVAL_REQUIRES_SEPARATE_USER=true
export ERASUREPROOF_APPROVAL_TTL_HOURS=24
~~~

A destructive run returns `428` until an administrator approves it. Approval is
single-use, expires, and is claimed atomically before remediation. Audit-only
runs (`?remediate=false`) do not require approval.

## Configuration

| Variable | Default | Notes |
|---|---|---|
| `ERASUREPROOF_ENVIRONMENT` | `development` | Production enables strict validation. |
| `ERASUREPROOF_DATA_DIR` | `./.erasureproof` | Evidence, ledger, attestations. |
| `ERASUREPROOF_DATABASE_URL` | SQLite | PostgreSQL is required for replicas. |
| `ERASUREPROOF_DEMO_ENABLED` | `true` | Disable in production. |
| `ERASUREPROOF_AUTH_MODE` | `disabled` | `disabled`, `api_key`, or `oidc`. |
| `ERASUREPROOF_API_KEYS` | empty | JSON list of key, role, tenant, subject. |
| `ERASUREPROOF_REQUIRE_REMEDIATION_APPROVAL` | `false` | Enable in production. |
| `ERASUREPROOF_APPROVAL_TTL_HOURS` | `24` | Minimum 1. |
| `ERASUREPROOF_RATE_LIMIT_PER_MINUTE` | `0` | Per-process, per-IP limit. |
| `ERASUREPROOF_TRUST_PROXY_HEADERS` | `false` | Enable only behind a trusted ingress. |
| `ERASUREPROOF_CORS_ORIGINS` | localhost Vite | Comma-separated exact origins. |
| `ERASUREPROOF_HSTS_SECONDS` | `0` | Set above zero behind TLS. |
| `ERASUREPROOF_METRICS_TOKEN` | empty | If set, required for `/metrics`. |
| `ERASUREPROOF_ATTESTATION_KEY` | dev key | Signs attestations and backups. |
| `ERASUREPROOF_EXPOSURE_ENABLED` | `false` | Opt in explicitly. |

Never commit secrets. Supply credentials through environment variables or a
managed secret store.

## Kubernetes

`deploy/kubernetes` runs at least two replicas against managed PostgreSQL and a
shared `ReadWriteMany` volume. It includes:

- API-key authentication and required remediation approval;
- startup, liveness, and readiness probes backed by `/livez` and `/readyz`;
- a non-root, read-only-root-filesystem container with dropped capabilities;
- HPA, ingress TLS, topology spread, and a default-deny network policy.

Create the `erasureproof-secrets` secret first; it is deliberately excluded from
Kustomize. See `deploy/kubernetes/README.md` for the full checklist.

## Backups

~~~bash
erasureproof backup create --output /secure/backups/erasureproof.zip
erasureproof backup verify /secure/backups/erasureproof.zip
~~~

The signed archive contains evidence objects, the ledger, attestations, and a
SQLite snapshot when the metadata store is SQLite. Back up PostgreSQL with your
provider's tooling in the same window. Restores refuse to overwrite live data
unless `--force` is supplied and the destination is outside the live data
directories.

## Operational checklist

- Persist the data directory on a shared, backed-up volume.
- Back up the signing key separately from attestations and archives.
- Rotate API keys by updating the secret and rolling the deployment.
- Restrict network egress for exposure scans and OIDC to known providers.
- Use `/readyz` for readiness, not `/healthz`.
- Export and retain tenant-scoped audit events.
- Verify the ledger and a recent backup after every restore.
- Monitor failed verification checks and `erasureproof_rate_limited_total`.
- Rotate signing keys with a documented re-attestation plan.

## Behind a proxy

Terminate TLS at your ingress. Forward `Host` and `X-Forwarded-For`. Only enable
`ERASUREPROOF_TRUST_PROXY_HEADERS` when the ingress is the sole network path to
the API, otherwise clients can spoof their source address. The SPA is served
under `/console`, the API under `/v1`, and OpenAPI under `/docs`.
