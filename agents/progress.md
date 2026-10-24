# Progress

Last updated: 2026-10-24

## Current milestone: M1/M2 — mostly done via persona management (2026-10-24)

Next steps:
1. Guardrail gaps: NER for third-party names that aren't participants (e.g. "Rahul" mentioned in text
   stays), and the LLM sensitive-topic classifier + review queue (FR-GRD-04, FR-GRD-06).
2. Voice cloning from the persona's own voice notes (FR-VOICE-02/03). Voice choice from a catalog is done (D-015);
   changing a persona's voice after creation isn't in the UI yet.
3. Mood detection of the user's message (FR-EMO-04); session summary (FR-CHAT-05).
4. Eval harness (FR-EVAL-*): hold-out pairs + blind sheet.

- 2026-10-24: switched to uv (D-011). Verified `uv run main.py` locally (start, reload, shutdown).
  Docker image NOT yet rebuilt/verified with uv (no Docker daemon available in that session).

## Milestones

- [x] **Persona management** (2026-10-24) — create persona from name + WhatsApp .txt/.zip, pick participant,
  consent gate, background build, select in UI, chat in persona, delete:
  - `app/ingest/whatsapp.py` (Android/iOS, 12/24h, D/M vs M/D, multi-line, zip) — FR-ING-01..03
  - `app/guardrails/` artifacts, PII (+ACCOUNT), participant pseudonymization, output guard, pipeline+report — FR-GRD-01,02,03(partial),07,08
  - `app/persona/` pairs, stats, index (numpy cosine), builder (argon card + emoji map, gemini-embedding-2) — FR-BLD-01..05, FR-EMO-01
  - `app/storage/personas.py` on-disk store; routes: GET/DELETE /personas/{id}, POST /personas/participants, POST /personas (202)
  - Frontend: persona select, New persona panel, build polling, persona card panel, delete
  - Voice picker at creation (catalog + ▶ Preview), persona voice used for TTS, 429 retry (D-015)
  - 64 tests (incl. privacy regression). Live: 652-msg synthetic chat built in 12.8 s; chat first token 1.2–1.6 s

- [x] **M0** Requirements docs (`docs/requirements/`) + `agents/` steering
- [x] **Demo slice** (2026-10-24) — thin end-to-end path with a synthetic persona, ahead of M1:
  - `app/llm/client.py` Gemini/Vertex streaming wrapper (D-008), `app/llm/prompts.py`
  - `app/persona/demo.py` synthetic "Rohan" persona (card + reply examples + emoji map)
  - `app/chat/service.py` SSE stream (`delta`/`done`/`error`) + `PrefixStripper`
  - `app/speech/cues.py` emoji→S2 cue conversion + validator (FR-TTS-01..03), `app/speech/tts.py` Fish TTS (FR-TTS-04,05)
  - Routes: `GET /personas`, `POST /chat/stream`, `POST /tts`
  - Frontend chat screen: streaming bubbles, ▶ Speak, auto-speak, "show voice script", stop
  - 24 tests green; verified live: first token ~1.1–1.6 s, TTS ~2.5–4 s; Vite proxy streams SSE unbuffered
  - Not yet: output guard (FR-GRD-08), session summary, persisted personas — later milestones
- [ ] **M1** WhatsApp parser + guardrail pipeline + `/personas`, `/ingest` + tests
  - [x] `app/ingest/models.py`, `whatsapp.py` — FR-ING-01..03 (05 bursts in persona/pairs.py)
  - [x] `artifacts.py`, `pii.py` — FR-GRD-01,02; [ ] `rules.py` operator exclusions — FR-GRD-05
  - [~] `pseudonymize.py` — participants only; NER for other names pending — FR-GRD-03
  - [x] `app/llm/client.py` — Gemini/Vertex wrapper (D-008)
  - [ ] `app/guardrails/topics.py` (needs OQ-3) — FR-GRD-04,06
  - [x] `app/guardrails/pipeline.py` + report — FR-GRD-07
  - [x] `app/storage/personas.py`, routes in `personas.py` — FR-PER-01..04
  - [x] Synthetic fixtures + privacy regression test
- [~] **M2** Persona build — done except memory/fact KB (FR-BLD-04), card editing (FR-BLD-06), holdout (FR-EVAL-01)
- [~] **M3** chat — done except mood detection and session summary
- [~] **M4** Expressive TTS — cues, validator, Fish TTS done; per-persona voice attach/clone pending
- [~] **M5** Frontend — personas, create/report, chat with audio done; review queue UI pending
- [ ] **M6** Eval harness, review queue UI, persona card editor
- [ ] **M7** Streaming TTS
- [ ] **M8** Optional LoRA fine-tune

## Blockers / waiting on user

- OQ-4 Voice-note material available?
- Validate the parser on a real export from the user's phone (tested so far on synthetic Android/iOS formats only)

## Notes

- 2026-10-24: LLM decided — Vertex AI Gemini via ADC; benchmarked (see knowledge/vertex-gemini.md).
- Existing code: FastAPI skeleton (health route, SPA serving), React+Vite health page, Docker, Makefile.
