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

RUN --mount=type=cache,target=/root/.cache/pip pip install ".[postgres,oidc]"

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app \
    && mkdir -p /data \
    && chown -R app:app /data

ENV ERASUREPROOF_DATA_DIR=/data \
    ERASUREPROOF_DATABASE_URL=sqlite:////data/erasureproof.db \
    ERASUREPROOF_POLICY_DIR=/app/policies \
    ERASUREPROOF_WEB_DIR=/app/web/dist \
    HOME=/tmp \
    XDG_CACHE_HOME=/tmp/.cache \
    PORT=8000

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f\"http://127.0.0.1:{os.environ.get('PORT', '8000')}/healthz\", timeout=3)"

CMD ["sh", "-c", "exec uvicorn erasureproof.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
