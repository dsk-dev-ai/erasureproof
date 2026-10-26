# Quickstart

## Requirements

- Python 3.10+ (3.11 or 3.12 recommended)
- Node.js 20+ for the web console
- `uv` is recommended, but `pip` works
- Optional: `tesseract-ocr` and `poppler-utils` for scanned PDFs and image OCR

## Backend setup

~~~bash
uv venv .venv
uv pip install --python .venv/bin/python -e ".[dev]"
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

The image includes OCR and document-processing dependencies so scanned PDFs and images work out of the box.
