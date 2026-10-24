# Progress

Last updated: 2026-10-24

## Current milestone: M1 — Ingestion + guardrails (not started)

## Milestones

- [x] **M0** Requirements docs (`docs/requirements/`) + `agents/` steering
- [ ] **M1** WhatsApp parser + guardrail pipeline + `/personas`, `/ingest` + tests
  - [ ] `app/ingest/models.py`, `whatsapp.py` (Android + iOS, multi-line) — FR-ING-01..05
  - [ ] `app/guardrails/artifacts.py`, `rules.py`, `pii.py` — FR-GRD-01,02,05
  - [ ] `app/guardrails/pseudonymize.py` — FR-GRD-03
  - [ ] `app/llm/client.py` — Gemini/Vertex wrapper (D-008)
  - [ ] `app/guardrails/topics.py` (needs OQ-3) — FR-GRD-04,06
  - [ ] `app/guardrails/pipeline.py` + report — FR-GRD-07
  - [ ] `app/storage/personas.py`, routes `personas.py`, `ingest.py` — FR-PER-01..04
  - [ ] Synthetic fixtures + privacy regression test
- [ ] **M2** Persona build (stats, card, emoji map, pairs + memory index)
- [ ] **M3** `/chat` text-only + LLM abstraction + output guard
- [ ] **M4** Expressive TTS (cues, validator, Fish TTS, voice attach/clone)
- [ ] **M5** Frontend (personas, ingest/report, chat with audio)
- [ ] **M6** Eval harness, review queue UI, persona card editor
- [ ] **M7** Streaming TTS
- [ ] **M8** Optional LoRA fine-tune

## Blockers / waiting on user

- OQ-4 Voice-note material available?
- A sample (or synthetic) WhatsApp export to validate the parser format

## Notes

- 2026-10-24: LLM decided — Vertex AI Gemini via ADC; benchmarked (see knowledge/vertex-gemini.md).
- Existing code: FastAPI skeleton (health route, SPA serving), React+Vite health page, Docker, Makefile.
