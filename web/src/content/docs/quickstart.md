# Quickstart

## Requirements

- Python 3.10+ (3.11 or 3.12 recommended)
- Node.js 20+ for the web console
- `uv` is recommended, but `pip` works
- Optional: `tesseract-ocr` and `poppler-utils` for scanned PDFs and image OCR

## Install from PyPI

~~~bash
pip install erasureproof
erasureproof demo
~~~

Install `erasureproof[postgres]`, `erasureproof[oidc]`, `erasureproof[s3]`, or
`erasureproof[temporal]` for optional integrations. The dependency-free API
client is published as `erasureproof-sdk`.

## Backend setup from source

~~~bash
uv venv .venv
uv pip install --python .venv/bin/python -e ".[dev,oidc]"
.venv/bin/erasureproof demo
~~~

The CLI demo seeds a fictional commerce platform, runs a GDPR erasure for Alice, remediates every copy, verifies the result, and writes a signed attestation under `.erasureproof/`.

Useful commands:

~~~bash
.venv/bin/erasureproof demo --json
.venv/bin/erasureproof demo --graph
.venv/bin/erasureproof ledger verify
.venv/bin/erasureproof scan ./exports --email alice@example.com
.venv/bin/erasureproof graph result.json --format dot
~~~

## API and demo workspace

~~~bash
.venv/bin/uvicorn erasureproof.main:app --reload --port 8000
curl -X POST http://localhost:8000/v1/demo/seed
~~~

Open `http://localhost:8000/docs` for the OpenAPI reference.

Local development defaults to `ERASUREPROOF_AUTH_MODE=disabled`. Production
startup refuses that default. For an API-key deployment:

~~~bash
export ERASUREPROOF_ENVIRONMENT=production
export ERASUREPROOF_AUTH_MODE=api_key
export ERASUREPROOF_ATTESTATION_KEY="$(openssl rand -hex 32)"
export ERASUREPROOF_API_KEYS='[{"key":"replace-me","role":"admin","tenant_id":"*","subject":"admin"}]'
export ERASUREPROOF_REQUIRE_REMEDIATION_APPROVAL=true
~~~

Then use the key button in the console top bar or send
`Authorization: Bearer <key>` with API calls. Tenant-scoped keys cannot read or
write another tenant's data.

## Web console

~~~bash
cd web
npm install
npm run dev
~~~

Vite serves the console at `http://localhost:5173` and proxies `/v1`, `/healthz`, and `/version` to `localhost:8000`.

Production build:

~~~bash
cd web
npm run build
~~~

The FastAPI application serves the built SPA under `/console`.

## Tests

~~~bash
.venv/bin/pytest
.venv/bin/ruff check .
cd web && npm run build
~~~

## Docker

~~~bash
docker build -t erasureproof .
docker run --rm -p 8000:8000 erasureproof
~~~

The image includes OCR, document-processing, PostgreSQL, and OIDC dependencies so
scanned PDFs and images work out of the box. For a hardened deployment, use
`docker compose -f docker-compose.production.yml` or
`deploy/kubernetes`.
