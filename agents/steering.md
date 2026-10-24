# Development steering

## Project in one line
Chatbot that replies with a real person's essence (learned from sanitized chat history) and speaks
in their cloned voice with expressive Fish Audio cues derived from their own emoji/emotion habits.

## Hard rules (never break)

1. **Privacy pipeline order is fixed:** artifacts → rules → PII regex → pseudonymize → topic
   classifier. Nothing reaches an external API, the vector store, or disk before the local steps.
2. **No raw chat persisted.** Uploads go to a temp dir, deleted in `finally`.
3. **No message text in logs**, exceptions, reports or API error bodies. Log ids, counts, timings.
4. **Synthetic test data only.** Tests must use a `tmp_path` data dir (override `get_settings`), never the real `data/`.
    No real chats, names, numbers in `tests/`, docs, or commits.
5. **Consent gate:** voice cloning and persona build require `persona.consent.confirmed`.
6. **Fish cues use S2 bracket syntax** `[happy]`, never S1 parentheses. See `knowledge/fish-audio.md`.
7. **Never commit** `.env`, `data/`, uploads, voice clips.
8. Secrets only via `Settings` (`app/core/config.py`); never hard-coded or logged.

## Code conventions (match existing code)

- **Python 3.13**, FastAPI, Pydantic v2, `pydantic-settings`. Lint/format with `ruff` (`make lint`, `make format`).
- **Config:** add a typed field to `Settings` **and** the key to `.env.example` (with a comment).
  Access via `from app.core.config import settings`, or `SettingsDep` in routes.
- **Routes:** one module per resource in `app/api/routes/`, `router = APIRouter(tags=[...])`,
  registered in `app/api/router.py`. Keep routes thin; logic lives in service modules.
- **External clients** (LLM, Fish, embeddings) are wrapped in one module each and injected with
  `Depends(...)` so tests override them via `app.dependency_overrides`.
- **Prompts** live in `app/llm/prompts.py` only — no inline prompt strings elsewhere.
- Type hints everywhere; Pydantic models for anything crossing a boundary (API, disk, LLM JSON).
- Comment density like the existing code: short docstrings on non-obvious functions, no narration.
- Async routes; wrap blocking SDK calls with `run_in_threadpool` if the SDK is sync.
- Frontend: React + Vite, call the backend only through `frontend/src/api.js`.
- **Python tooling is uv.** Dependencies only via `uv add <pkg>` / `uv add --dev <pkg>` (updates
  `pyproject.toml` + `uv.lock`; commit both). Never `pip install`, never hand-edit `uv.lock`, no
  `requirements*.txt`. Run things with `uv run …` (`uv run main.py`, `uv run pytest`).
- Add a dependency only when the milestone needs it, with a lower bound.
- Entry point: root `main.py` (uvicorn from `Settings`); `app/main.py` is the FastAPI app.

## Design defaults

- LLM writes like the person **with emojis**; cues are derived deterministically from emojis
  (`app/speech/cues.py`). Don't ask the reply LLM to write Fish cues.
- Display text and TTS text are always separate outputs.
- Retrieval is per-persona; never query across personas.
- Prefer deterministic code over LLM calls where feasible (stats, parsing, regex, cue validation).
- When unsure between DROP and REDACT in guardrails, REDACT (keeps style), unless the topic is in the DROP list.

## Definition of done (any task)

- [ ] Code follows conventions above; `make lint` clean.
- [ ] Tests added/updated; `make test` green; external APIs mocked.
- [ ] New settings in `Settings` + `.env.example`.
- [ ] Privacy check: no raw text logged/persisted; synthetic fixtures only.
- [ ] Requirement IDs touched are mentioned in the commit/PR description.
- [ ] `agents/progress.md` updated; `agents/decisions.md` appended if a choice was made.

## How to verify things

- Backend: `uv run main.py` (or `make run`), then `curl localhost:8000/api/v1/...`; docs at `/docs` (non-prod).
  For a throwaway test server use another port: `PORT=8766 uv run main.py --no-reload`.
- Frontend: `make web` → http://localhost:5173 (proxies `/api`).
- Tests: `make test` (= `uv run pytest -q`). Live API smoke tests: `uv run pytest -m live` (needs keys; opt-in).
