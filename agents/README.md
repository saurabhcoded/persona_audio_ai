# agents/ — steering for AI coding agents

Read this folder **before** starting any task in this repo. It's the agent's working memory:
how we build, what's decided, where we are.

| File | Read when |
|---|---|
| [steering.md](steering.md) | Always. Conventions, rules, definition of done. |
| [progress.md](progress.md) | Always. Current milestone, what's done, what's next. |
| [decisions.md](decisions.md) | Before making a design choice. Append new decisions here. |
| [workflows/dev-workflow.md](workflows/dev-workflow.md) | Starting any feature or fix. |
| [workflows/ingestion-pipeline.md](workflows/ingestion-pipeline.md) | Touching `app/ingest/` or `app/guardrails/`. |
| [workflows/persona-build.md](workflows/persona-build.md) | Touching `app/persona/` or `app/retrieval/`. |
| [workflows/chat-pipeline.md](workflows/chat-pipeline.md) | Touching `app/chat/`, `app/llm/`, `app/speech/`. |
| [knowledge/fish-audio.md](knowledge/fish-audio.md) | Anything that produces TTS text or calls Fish Audio. |
| [knowledge/vertex-gemini.md](knowledge/vertex-gemini.md) | Anything that calls an LLM or embeddings (Gemini on Vertex AI). |
| [knowledge/google-maps.md](knowledge/google-maps.md) | Anything in `app/location/` (Places, Routes, Uber links). |
| [knowledge/deployment.md](knowledge/deployment.md) | Deploying / anything about the Cloud Run service. |
| [knowledge/related-projects.md](knowledge/related-projects.md) | Looking for prior art / ideas. |

Architecture overview with pipeline diagrams: [`docs/architecture/README.md`](../docs/architecture/README.md).
Product requirements live in [`docs/requirements/`](../docs/requirements/README.md); requirement IDs
(`FR-*`, `NFR-*`) referenced here come from there.

## Keeping this folder current

- Finish a task → update `progress.md` (check items off, note next step).
- Make or change a design choice → append to `decisions.md`.
- Learn a non-obvious fact (API quirk, gotcha) → add to the relevant `knowledge/` or workflow file.
- Keep files short and factual; delete what's no longer true.
