# syntax=docker/dockerfile:1

# ---------- frontend: build React app ----------
FROM node:24-alpine AS frontend

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---------- base ----------
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# ---------- dev: hot reload, dev deps ----------
FROM base AS dev

COPY requirements.txt requirements-dev.txt ./
RUN pip install -r requirements-dev.txt

COPY . .

CMD ["sh", "-c", "uvicorn app.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8000} --reload"]

# ---------- prod: slim, non-root ----------
FROM base AS prod

COPY requirements.txt ./
RUN pip install -r requirements.txt

RUN useradd --create-home --uid 1000 appuser
COPY --chown=appuser:appuser app ./app
COPY --from=frontend --chown=appuser:appuser /frontend/dist ./frontend/dist
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.getenv(\"PORT\",\"8000\")}{os.getenv(\"API_V1_PREFIX\",\"/api/v1\")}/health')" || exit 1

CMD ["sh", "-c", "exec uvicorn app.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8000} --workers ${WORKERS:-1} --proxy-headers"]
