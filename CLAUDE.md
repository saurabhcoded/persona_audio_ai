# CLAUDE.md

Persona Voice: a chatbot that replies with a real person's essence (from sanitized chat history)
and speaks in their cloned voice with expressive Fish Audio cues.

**Before any task, read:**
1. `agents/steering.md` — hard rules (privacy!), conventions, definition of done
2. `agents/progress.md` — current milestone and next step
3. The workflow in `agents/workflows/` for the area you're touching
4. `agents/decisions.md` before making a design choice

Requirements: `docs/requirements/` (IDs `FR-*`, `NFR-*`). Fish Audio syntax/API: `agents/knowledge/fish-audio.md`.
LLM: Gemini on Vertex AI via gcloud ADC — `agents/knowledge/vertex-gemini.md`.

After finishing a task, update `agents/progress.md` and append to `agents/decisions.md` if you decided something.

Python is managed with **uv** (`pyproject.toml` + `uv.lock`; add deps with `uv add`, never pip).
Commands: `uv sync` · `uv run main.py` (API) · `make web` (frontend) · `uv run pytest -q` · `make lint` · `make format` · `make dev` (Docker).
