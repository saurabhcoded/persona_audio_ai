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

COPY --from=ghcr.io/astral-sh/uv:0.12.10 /uv /bin/uv

# The venv lives outside /app so dev bind-mounts don't hide it.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH

WORKDIR /app

# ---------- dev: hot reload, dev deps ----------
FROM base AS dev

COPY pyproject.toml uv.lock ./
RUN uv sync --locked

COPY . .

CMD ["python", "main.py", "--reload"]

# ---------- prod: slim, non-root ----------
FROM base AS prod

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-cache

RUN useradd --create-home --uid 1000 appuser
COPY --chown=appuser:appuser main.py ./
COPY --chown=appuser:appuser app ./app
COPY --from=frontend --chown=appuser:appuser /frontend/dist ./frontend/dist
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.getenv(\"PORT\",\"8000\")}{os.getenv(\"API_V1_PREFIX\",\"/api/v1\")}/health')" || exit 1

CMD ["python", "main.py", "--no-reload"]
