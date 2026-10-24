# Decision log

Append-only. Format: `D-NNN · date · status (proposed/accepted/superseded) · decision — why`.
Open questions (OQ-*) mirror `docs/requirements/product-requirements.md` §9.

## Accepted

- **D-001 · 2026-10-24 · accepted** — TTS via Fish Audio `s2.1-pro` with S2 bracket cues; no S1.
  *Why:* S2 supports free-form natural-language cues; S1 is deprecated (retires 2026-12-31) and its
  parentheses are not auto-converted.
- **D-002 · 2026-10-24 · accepted** — Retrieval of the persona's **real past replies** (context→reply
  pairs) is the primary style mechanism; persona card is secondary. Fine-tuning deferred to M8.
  *Why:* exemplars transfer humor/rhythm better than descriptions; no GPU needed; avoids WeClone-style training cost.
- **D-003 · 2026-10-24 · accepted** — Emojis are interpreted **per person** (learned emoji map), not via a fixed table.
  *Why:* emoji meaning is idiosyncratic (🙂 can be passive-aggressive, 💀 = laughing).
- **D-004 · 2026-10-24 · accepted** — Reply LLM writes plain persona text with emojis; Fish cues are derived
  deterministically from emojis/markers. Display text and TTS text are separate.
  *Why:* cues reflect the person's real habits; keeps UI clean; cue syntax validated in code.
- **D-005 · 2026-10-24 · accepted** — Guardrail runs before storage/embedding/external calls; local steps
  (regex, pseudonymize) precede any LLM classification. Raw exports never persisted.
- **D-006 · 2026-10-24 · accepted** — Build our own stack rather than fork WeClone.
  *Why:* WeClone needs 16GB+ GPU, WhatsApp support "coming soon", AGPL-3.0, no expressive cues. Borrow ideas only.
- **D-007 · 2026-10-24 · accepted** — First data source: WhatsApp exports (Android + iOS formats).

- **D-008 · 2026-10-24 · accepted** (resolves OQ-1, supersedes proposed D-101) — LLM = **Gemini on Vertex AI**
  via the user's gcloud ADC (project `eseller-ai`, location `global`), `google-genai` SDK with `vertexai=True`,
  behind `app/llm/client.py`. Model per job:
  - Live chat reply + mood: `gemini-3.5-flash-lite`, `thinkingLevel=low` (~1.0–1.2 s measured).
  - Offline build (persona card, emoji map, emotional baseline): `gemini-4-argon` (best in-character quality, ~3–6 s; latency irrelevant offline).
  - Guardrail topic classifier (many windows): `gemini-3.5-flash-lite` (cheap, fast).
  - Embeddings: `gemini-embedding-2`.
  - Optional "quality mode" for chat: `gemini-4-argon` via setting.
  *Why:* user's choice of provider; benchmark in `knowledge/vertex-gemini.md`.

- **D-009 · 2026-10-24 · accepted** — Chat streaming = `POST /chat/stream` returning **SSE** (`text/event-stream`),
  events `delta {text}`, `done {bubbles, tts_text}`, `error {message}`. Client sends the turn history
  (stateless server for now). Frontend reads it with `fetch` + stream reader (EventSource can't POST).
  TTS is a separate `POST /tts` with the `tts_text`, so text never waits for audio.
- **D-010 · 2026-10-24 · accepted** — Until M1/M2, personas come from `app/persona/demo.py` (synthetic only).
  Real personas will load from `data/personas/<id>/` behind the same `get_persona()`.

- **D-011 · 2026-10-24 · accepted** — Python managed with **uv** (user's choice): `pyproject.toml` +
  `uv.lock` (dev tools in `dev` group, `package = false`), `requirements*.txt` removed. Root `main.py`
  runs uvicorn from `Settings` so `uv run main.py` starts the API (reload default on when
  `ENVIRONMENT=local`; `--reload/--no-reload`). Docker copies uv from `ghcr.io/astral-sh/uv:0.12.10`,
  installs with `uv sync --locked` into `/opt/venv`, runs `python main.py`.

- **D-012 · 2026-10-24 · accepted** (resolves OQ-2, replaces proposed D-102) — Retrieval index = per-persona
  **numpy flat cosine index** (`vectors.npy` + `pairs.jsonl`, `app/persona/index.py`), cached by mtime.
  *Why:* a chat yields ≤ a few thousand pairs; flat search is ~ms, no extra service. Revisit Chroma if
  personas exceed ~50k pairs or memories/facts need filtering.
- **D-013 · 2026-10-24 · accepted** — Persona creation is two calls: `POST /personas/participants` (parse in
  memory, return senders, store nothing) then `POST /personas` (multipart: name, sender, consent, file) →
  sanitize in the request, save persona as `building`, build in a FastAPI BackgroundTask. UI polls `GET /personas`.
  The file is uploaded twice rather than kept server-side, so raw exports are never persisted (FR-ING-04).
- **D-014 · 2026-10-24 · accepted** — Pseudonymization keeps the persona and, in 1:1 chats, the other person
  (the operator); group-chat participants become `Person_N` (`Contact_N` for unsaved numbers). Name replacement
  in text is case-sensitive and skips role words (bhai, mummy, …) so style words survive. Output guard strips
  any `Person_N` / placeholders the model copies.

- **D-015 · 2026-10-24 · accepted** — Persona voice is chosen at creation from a fixed catalog
  (`app/speech/voices.py`, `GET /voices`): 2 female + 2 male English library voices + user's Girl Hindi /
  Boy Hindi. Stored as `persona.voice_id`; `POST /tts` accepts `voice_id` (catalog-only) for previews.
  Cloning from the persona's own voice notes stays future work (FR-VOICE-02).

- **D-016 · 2026-10-24 · accepted** — Speech streams with the text: `POST /chat/stream` with `speak: true`
  sends each finished line to Fish as soon as the model writes it (`app/chat/speaker.py`, ≤2 parallel TTS calls),
  and emits `audio {index, format, audio(base64)}` / `audio_error {index}` events in line order in the same SSE
  stream. The browser plays clips back to back (`frontend/src/audioQueue.js`) and keeps them for replay.
  Same output guard + emoji→cue conversion per line as the final `tts_text`. Pending TTS is cancelled if the
  client disconnects. *Why not Fish websocket streaming:* lines are short (~0.3–0.6 s to synthesize), so
  per-line HTTP gives most of the gain without MediaSource-based partial-mp3 playback; revisit for long replies.
- **D-017 · 2026-10-24 · accepted** — Chat model thinking level `minimal` (was `low`): same style, first-token
  p50 0.77 s / max 0.94 s vs low 0.82 s / 1.96 s. Empty model replies are retried once.

- **D-018 · 2026-10-24 · accepted** (user preference) — A single laugh emoji attached to text is voiced with
  `[joking]` instead of `[laughing] hahaha`; ≥2 laugh emojis or an emoji-only laugh keep the real laugh.
  `[joking]` is free-form S2 (not in Fish's listed vocabulary) — verified it synthesizes.

- **D-019 · 2026-10-24 · accepted** (branch `feature/location-assist`) — Location assist via **Gemini function
  calling inside the persona chat stream**: tools `plan_ride(origin, destination)` and `save_place(label, place)`
  (`app/location/assistant.py`); up to 3 tool rounds per reply; Gemini 3 call parts are echoed back whole
  (thought signatures). Server resolves places (saved labels → `place_id:` → Places text search → own
  ambiguity check) so the model only decides *when* to call and *what to ask*. Model sees labels/names and
  route numbers, never saved addresses; full addresses + deep links go to the UI as `location` /
  `choices` / `saved_place` SSE events. Ride = Routes API distance + traffic time + Uber universal link
  (no fares). Google auth via gcloud ADC (APIs enabled on eseller-ai with user approval).
- **D-020 · 2026-10-24 · accepted** — Saved places are per user, not per persona: `DATA_DIR/places.json`,
  saved by telling any persona ("ghar sector 21C faridabad hai"), listed/deleted in the sidebar
  (`GET /places`, `DELETE /places/{label}`). Labels normalized (my/mera/ghar→home, work→office).

- **D-021 · 2026-10-24 · accepted** (user requirement: "ask proper details before finalising") — Rides are
  two-step. (1) Exact places only: a whole city/district/PIN (`BROAD_TYPES`) is `too_broad` and the persona
  asks for an area/landmark/address; everything unclear is reported together. (2) `plan_ride(confirmed=false)`
  emits `ride_preview` (draft card, no links) + `draft` refs; the client keeps it and sends `pending_ride`
  with the next message. A plain yes (`is_confirmation`: "Confirm ✅", "haan book kar do", "ok") confirms
  **server-side** (no model call needed) and emits the final `location` card; anything else goes to the
  model with the pending draft in the prompt. *Why server-side:* the model announced "abhi karta hu"
  without calling the tool. Refs use labels for saved places, so addresses still never reach the model.
- **D-022 · 2026-10-24 · accepted** — Chat with location tools uses `LLM_TOOLS_MODEL=gemini-3.5-flash`
  (minimal thinking). Measured tool-call rate on persona prompts: flash-lite minimal 0/5, flash-lite low 1/5,
  3.5-flash minimal 12/12 (~1.1 s), argon 5/5 (~4.3 s), 3.7-flash slow (6–17 s). Chat streams now retry
  429/500/503 when nothing has been streamed yet (a Vertex 429 broke a live confirm turn).

- **D-023 · 2026-10-24 · accepted** — Voice management. Persona voice can be changed any time
  (`PATCH /personas/{id}/voice`, picker in the profile panel; demo persona's change stored in
  `personas/builtin_overrides.json`; a build in progress keeps a voice changed meanwhile and doesn't recreate
  a persona deleted mid-build). Custom voices are added by Fish voice ID (`POST /voices` → validated with
  Fish `voices.get`, name/gender/language from its title/tags/languages) into `DATA_DIR/voices.json`,
  listed after the built-ins, removable (`DELETE /voices/{id}`, built-ins protected). UI: sidebar → Voices.

## Proposed (need user confirmation)

- **D-103 · proposed** — Topic classifier: cheap external LLM on already-redacted text; Llama Guard local as
  fallback for stricter privacy. → OQ-3
- **D-104 · proposed** — PII/NER: Presidio + custom UPI/IFSC regex; GLiNER optional for Hinglish names.

## Open questions

- ~~OQ-1 LLM provider~~ → D-008. ~~OQ-2 Vector store~~ → D-012. **OQ-3** Classifier locality. **OQ-4** Voice-note material.
