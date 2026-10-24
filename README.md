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

## Deploy (Google Cloud Run)

`make deploy` builds the image with Cloud Build and deploys service `persona-voice` to project
`eseller-ai` (asia-south1). Data lives in a private Cloud Storage bucket mounted at `/data`; the Fish
Audio key comes from Secret Manager. Live: https://persona-voice-627395208842.asia-south1.run.app
(public, no login yet). Details and one-time setup: `agents/knowledge/deployment.md`.

## Run locally

Python is managed with [uv](https://docs.astral.sh/uv/): dependencies live in `pyproject.toml`
(dev tools in the `dev` group) and are pinned in `uv.lock`.

```bash
uv sync                      # create .venv and install everything from uv.lock
uv run main.py               # API on :8000 (auto-reload when ENVIRONMENT=local)
uv run main.py --no-reload   # or --reload to force it on
uv add <package>             # add a runtime dependency (updates pyproject + lock)
uv add --dev <package>       # add a dev-only dependency

make run      # same as `uv run main.py`
make web      # Vite dev server on :5173 (proxies /api to :8000)
make web-build  # build SPA so FastAPI serves it at :8000
make test
make lint
```

### Demo chat

Needs `gcloud auth application-default login` (Gemini on Vertex AI) and `FISH_AUDIO_API_KEY` in
`.env` (for voice). Run `uv run main.py` and `make web`, open http://localhost:5173 and chat with the
synthetic demo persona. Replies stream in and, with **Speak replies** on, each line is spoken as soon as
it's written (Fish Audio, emoji-derived expression cues); **▶ Speak** replays ("Show voice script" displays the cued text).

**Personas:** click **+ New**, upload a WhatsApp export (chat → ⋮ → More → Export chat → Without media),
pick which participant the persona is, choose a voice (▶ Preview to listen), confirm consent, and create.
Short forms from the chat ("r u", "kb", "h" = hai) are detected per persona and listed in its profile:
by default the voice says them in full while the text keeps the persona's style; edit the list, add your
own, or switch on "Show in full".
Change a persona's voice any time from its profile panel. Add more Fish Audio voices under
**Voices** (sidebar): paste a voice ID from its fish.audio URL; name and language are filled in. The chat is sanitized (phone numbers,
emails, IDs, account/card numbers, links, other group members' names) before anything is stored; the
uploaded file itself is never saved. Not yet removed: names of people who are only mentioned in messages,
and sensitive topics (see `agents/progress.md`). The build (style stats, persona card, emoji→voice map, reply index) runs in the background,
usually under a minute, then select the persona and chat. Data lives in `DATA_DIR` (`data/`, git-ignored).

**Location assist:** ask any persona for a ride: *"new delhi se faridabad uber dekh"* or *"mere ghar se
sector 15"*. It first collects exact details: a city alone isn't enough, so it asks for the area or landmark,
which Sector 15, or where home is, and remembers places you tell it ("ghar sector 21C faridabad hai";
saved places show in the sidebar). Then it shows a **draft** (pickup, drop, distance, time with live
traffic) for you to check; after you tap **Confirm** (or say "haan"), it shows the final card with
**Open in Uber** (pickup/drop pre-filled) and **Google Maps**. Uses gcloud credentials; the Places and Routes APIs must be enabled on the project.

API: `GET/POST /api/v1/personas`, `POST /api/v1/personas/participants`, `GET/DELETE /api/v1/personas/{id}`,
`POST /api/v1/chat/stream` (SSE), `POST /api/v1/tts`, `GET /api/v1/voices`, `GET/DELETE /api/v1/places`.
Project docs: `docs/requirements/`, agent steering: `agents/`.

Health check: `GET /api/v1/health`. `/docs` and `/redoc` are disabled when `ENVIRONMENT=prod`.

## Frontend

- Dev: Vite serves the app and proxies `/api` to FastAPI (`VITE_API_PROXY_TARGET`,
  default `http://localhost:8000`), so no CORS is needed.
- Prod: the Docker build compiles the app and FastAPI serves `frontend/dist`. Any non-API
  path returns `index.html`, so client-side routing works.
- Call the backend through `src/api.js` (`apiGet("/health")`); base is `/api/v1`, override with
  `VITE_API_BASE`.
