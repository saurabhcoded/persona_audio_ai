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

## Proposed (need user confirmation)

- **D-102 · proposed** — Vector store: Chroma, persistent, local, one collection set per persona. → OQ-2
- **D-103 · proposed** — Topic classifier: cheap external LLM on already-redacted text; Llama Guard local as
  fallback for stricter privacy. → OQ-3
- **D-104 · proposed** — PII/NER: Presidio + custom UPI/IFSC regex; GLiNER optional for Hinglish names.

## Open questions

- ~~OQ-1 LLM provider~~ → D-008. **OQ-2** Vector store. **OQ-3** Classifier locality. **OQ-4** Voice-note material.
