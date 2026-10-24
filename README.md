# Fish Audio API

FastAPI service with `.env`-based configuration (via `pydantic-settings`), a React + Vite
single-page frontend, and Docker.

## Layout

```
app/
  main.py            # FastAPI app factory, middleware, routers
  core/config.py     # Settings (reads env vars + .env)
  core/logging.py
  api/router.py      # Aggregates route modules
  api/routes/        # One module per resource
  frontend.py        # Serves frontend/dist with SPA fallback
frontend/            # React + Vite app (src/App.jsx, src/api.js)
tests/
Dockerfile           # multi-stage: frontend build, `dev` (reload), `prod` (non-root, serves SPA)
docker-compose.yml   # prod-like: one container, API + built SPA on :8000
docker-compose.dev.yml  # dev override: hot reload API + Vite dev server on :5173
```

## Configuration

All settings live in `app/core/config.py`. Values are loaded in this order (highest wins):

1. Real environment variables (e.g. from Docker / CI)
2. `.env` file
3. Defaults in `Settings`

```bash
cp .env.example .env
```

Use it anywhere with `from app.core.config import settings`, or inject it in routes
with `Depends(get_settings)` (overridable in tests via `app.dependency_overrides`).

To add a setting: add a typed field to `Settings` and the matching key to `.env.example`.

## Run with Docker

```bash
make dev    # API (:8000, reload) + Vite (:5173, HMR) -> http://localhost:5173
make up     # prod-like single container -> http://localhost:8000
make down
```

Without make:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
docker compose up --build -d
```

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate   # or: uv venv
pip install -r requirements-dev.txt
make run      # uvicorn with reload on :8000
make web      # Vite dev server on :5173 (proxies /api to :8000)
make web-build  # build SPA so FastAPI serves it at :8000
make test
make lint
```

Health check: `GET /api/v1/health`. `/docs` and `/redoc` are disabled when `ENVIRONMENT=prod`.

## Frontend

- Dev: Vite serves the app and proxies `/api` to FastAPI (`VITE_API_PROXY_TARGET`,
  default `http://localhost:8000`), so no CORS is needed.
- Prod: the Docker build compiles the app and FastAPI serves `frontend/dist`. Any non-API
  path returns `index.html`, so client-side routing works.
- Call the backend through `src/api.js` (`apiGet("/health")`); base is `/api/v1`, override with
  `VITE_API_BASE`.
