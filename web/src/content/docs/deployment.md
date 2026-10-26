# Deployment

## Local

~~~bash
uv venv .venv
uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/uvicorn erasureproof.main:app --port 8000
~~~

## Docker

The image is multi-stage: the frontend is built with Node, then copied into a Python runtime that includes OCR and document tooling.

~~~bash
docker build -t erasureproof .
docker run --rm -p 8000:8000 \
  -e ERASUREPROOF_ENVIRONMENT=production \
  -e ERASUREPROOF_EXPOSURE_ENABLED=false \
  -v erasureproof-data:/data \
  erasureproof
~~~

Set `ERASUREPROOF_DATA_DIR=/data` when mounting a volume.

## Configuration

| Variable | Default | Notes |
|---|---|---|
| `ERASUREPROOF_ENVIRONMENT` | `development` | Runtime label. |
| `ERASUREPROOF_DATA_DIR` | `./.erasureproof` | Evidence, ledger, attestations. |
| `ERASUREPROOF_DATABASE_URL` | SQLite | PostgreSQL is supported. |
| `ERASUREPROOF_DEMO_ENABLED` | `true` | Disable in production if undesired. |
| `ERASUREPROOF_EXPOSURE_ENABLED` | `false` | Opt in explicitly. |
| `ERASUREPROOF_SIGNING_KEY` | generated | HMAC key for attestations. |

Never commit secrets. Supply credentials through environment variables or a managed secret store.

## Operational checklist

- Persist the data directory.
- Back up the signing key separately from attestations.
- Restrict network egress for exposure scans.
- Run `GET /healthz` as a readiness probe.
- Verify the ledger after restore.
- Monitor failed verification checks.
- Rotate signing keys with a documented re-attestation plan.

## Behind a proxy

Terminate TLS at your ingress. Forward `Host` and `X-Forwarded-*` headers. The SPA is served under `/console`, the API under `/v1`, and OpenAPI under `/docs`.
