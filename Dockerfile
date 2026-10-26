FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY policies ./policies

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        poppler-utils \
        tesseract-ocr \
        libimage-exiftool-perl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install ".[postgres]"

RUN mkdir -p /data

ENV ERASUREPROOF_DATA_DIR=/data \
    ERASUREPROOF_DATABASE_URL=sqlite:////data/erasureproof.db \
    ERASUREPROOF_POLICY_DIR=/app/policies

EXPOSE 8000

CMD ["uvicorn", "erasureproof.main:app", "--host", "0.0.0.0", "--port", "8000"]
