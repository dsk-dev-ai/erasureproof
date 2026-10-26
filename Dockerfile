# syntax=docker/dockerfile:1.7

FROM node:20-bookworm-slim AS console

WORKDIR /app/web

COPY web/package.json web/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm config set fetch-retries 5 \
    && npm config set fetch-retry-maxtimeout 120000 \
    && npm config set fetch-timeout 600000 \
    && npm ci --no-audit --no-fund --prefer-offline

COPY web/ ./
RUN npm run build

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY policies ./policies
COPY --from=console /app/web/dist ./web/dist

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        poppler-utils \
        tesseract-ocr \
        libimage-exiftool-perl \
    && rm -rf /var/lib/apt/lists/*

RUN --mount=type=cache,target=/root/.cache/pip pip install ".[postgres]"

RUN mkdir -p /data

ENV ERASUREPROOF_DATA_DIR=/data \
    ERASUREPROOF_DATABASE_URL=sqlite:////data/erasureproof.db \
    ERASUREPROOF_POLICY_DIR=/app/policies \
    ERASUREPROOF_WEB_DIR=/app/web/dist

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3)"

CMD ["uvicorn", "erasureproof.main:app", "--host", "0.0.0.0", "--port", "8000"]
