# Technical Design — Persona Voice

Status: Draft v0.1 · 2026-10-24 · Implements [product-requirements.md](product-requirements.md)

## 1. Architecture

```
                 ┌─────────────── INGEST (offline, per persona) ───────────────┐
WhatsApp export ─► parse ─► guardrail (artifacts → PII → pseudonymize → rules → topics)
                                   │  raw text discarded here
                                   ▼
                          sanitized messages (data/personas/<id>/messages.jsonl)
                                   │
          ┌──────────────┬─────────┴─────────┬──────────────────┐
          ▼              ▼                   ▼                  ▼
     style stats    persona card        emoji map         reply pairs + memories
     (deterministic) (LLM)              (LLM per emoji)    (embeddings → vector store)
                 └───────────────────────────────────────────────────────────────┘

                 ┌────────────────────── CHAT (per request) ─────────────────────┐
user message ─► mood detect ─► retrieve (pairs, memories) ─► LLM in-persona reply
                                                                  │
                                                       output guard (PII scan)
                                                                  │
                                         ┌────────────────────────┴───────┐
                                         ▼                                ▼
                                  display text (emojis)       emoji→cue + validate
                                                                          │
                                                               Fish Audio TTS (s2.1-pro,
                                                               persona voice) ─► audio
                 └───────────────────────────────────────────────────────────────┘
```

## 2. Module layout

Follows the existing conventions (`app/api/routes/` one module per resource, settings via
`app.core.config`).

```
app/
  api/routes/
    health.py          (exists)
    personas.py        create / get / list / delete, consent
    ingest.py          upload export, report, review queue
    build.py           trigger persona build, get card / emoji map
    voice.py           attach voice id, upload clips
    chat.py            POST /chat
  core/                config.py, logging.py (exist)
  ingest/
    models.py          Message, Burst
    whatsapp.py        parser (Android + iOS formats)
  guardrails/
    artifacts.py       drop WhatsApp system/media lines
    pii.py             regex + Luhn redaction
    pseudonymize.py    consistent name/place pseudonyms
    rules.py           contact/keyword/date exclusions
    topics.py          windowed sensitive-topic classifier
    output.py          reply-time PII scan
    pipeline.py        sanitize_chat() orchestration + report
  persona/
    stats.py           deterministic style stats
    card.py            persona card extraction
    emoji_map.py       person-specific emoji meanings
    pairs.py           reply-pair construction + holdout split
    memory.py          memory chunking / fact extraction
  retrieval/
    store.py           vector store wrapper (per-persona collections)
  llm/
    client.py          provider-agnostic interface: complete(), classify_json()
    prompts.py         all prompt templates in one place
  speech/
    cues.py            emoji→cue conversion, cue validator, strip_cues()
    tts.py             Fish Audio TTS wrapper
    voice.py           voice reference / cloning
  chat/
    service.py         chat orchestration
    sessions.py        session turns + rolling summary
  storage/
    personas.py        on-disk persona repository (data/personas/<id>/)
data/                  git-ignored runtime data
tests/
  fixtures/            SYNTHETIC chat exports only
```

## 3. Data model

```python
class Message(BaseModel):          # app/ingest/models.py
    ts: datetime
    sender: str
    text: str

class Persona(BaseModel):
    id: str                         # slug/uuid
    display_name: str
    export_name: str                # persona's name in the export
    operator_name: str              # operator's name in the export
    consent: ConsentRecord          # basis, attested_at, attested_by
    voice: VoiceConfig | None       # reference_id | reference clip paths
    status: Literal["created", "ingested", "built", "ready"]

class ReplyPair(BaseModel):
    id: str
    context: str                    # last ≤4 messages before persona's reply
    reply: str                      # persona's burst
    ts: datetime
    holdout: bool = False

class EmojiMeaning(BaseModel):
    meaning: str
    fish_cue: str                   # e.g. "[laughing]"
    spoken_as: str                  # e.g. "hahaha"
    count: int

class SanitizationReport(BaseModel):
    messages_in: int
    messages_out: int
    pii: dict[str, int]             # label -> count
    windows: dict[str, int]         # KEEP/REDACT/DROP -> count
    excluded_by_rule: int
    review_pending: int
```

### On-disk layout (per persona)
```
data/personas/<id>/
  persona.json            Persona
  messages.jsonl          sanitized messages
  pseudonyms.json         real→pseudonym map (local only, never sent to LLM/UI)
  report.json             SanitizationReport
  review.jsonl            pending review windows (redacted text)
  style_stats.json
  persona_card.json
  emoji_map.json
  voice/                  reference clips + transcripts
  vectors/                vector store (collections: pairs, memories)
```

## 4. API contracts (prefix `/api/v1`)

| Method & path | Body | Returns |
|---|---|---|
| `POST /personas/participants` *(built)* | multipart `file` | `{participants: [{name, messages}], total_messages}` — nothing stored |
| `POST /personas` *(built)* | multipart `name, sender, consent, file[, consent_basis]` | `202` summary, `status: building`; background build |
| `GET /personas` / `GET /personas/{id}` *(built)* | — | summaries / detail (card, style, stats, report, emoji_map) |
| `DELETE /personas/{id}` *(built)* | — | `204` (full erase; demo persona → 400) |
| `POST /personas/{id}/ingest` | multipart `file` (.txt/.zip), `rules` JSON | `{participants, report}` |
| `GET /personas/{id}/review` / `POST /personas/{id}/review` | `{window_id, decision}` | queue / `204` |
| `POST /personas/{id}/build` | — | `{style_stats, card, emoji_map, pairs_indexed}` |
| `GET/PUT /personas/{id}/card` | card JSON | card |
| `POST /personas/{id}/voice` | `{reference_id}` or multipart clips + transcripts | `VoiceConfig` |
| `POST /chat/stream` *(built)* | `{persona_id, turns: [{role: user\|persona, text}], speak?: bool, pending_ride?: {origin_ref, destination_ref, origin_name, destination_name}}` | SSE: `delta {text}`… `done {bubbles, tts_text}` or `error {message}`; location assist adds `ride_preview {draft card, draft refs}`, `location {confirmed ride card}`, `choices {options}`, `saved_place {label, name, address}`; with `speak`: `audio {index, format, audio}` / `audio_error {index, message}` per line, in order, interleaved |
| `POST /tts` *(built)* | `{text, persona_id?, voice_id?}` (`tts_text` with cues; `voice_id` catalog-only, overrides persona) | `audio/mpeg` bytes |
| `GET /places` / `DELETE /places/{label}` *(branch)* | — | saved places `[{label, name, address}]` / `204` |
| `GET /voices` *(built)* | — | built-in + custom voices `[{id, name, gender, language, description, custom}]` |
| `POST /voices` / `DELETE /voices/{id}` *(branch)* | `{voice_id, name?}` | add a Fish voice by ID (422 bad/unknown id, 409 built-in) / remove a custom voice |
| `PUT /personas/{id}/shortforms` *(branch)* | `{shortforms: [{short, full, enabled}], expand_shortforms_in_speech, expand_shortforms_in_text}` | persona detail |
| `POST /personas/{id}/shortforms/detect` *(branch)* | — | persona detail (re-detected, user edits kept; 400 without a stored chat) |
| `PATCH /personas/{id}/voice` *(branch)* | `{voice_id \| null}` | updated persona summary |

Errors: `409` persona not built/voice missing, `422` validation, `403` voice action without consent.

## 5. Pipelines

### 5.1 Ingestion → see `agents/workflows/ingestion-pipeline.md`
### 5.2 Persona build → see `agents/workflows/persona-build.md`
### 5.3 Chat + expressive TTS → see `agents/workflows/chat-pipeline.md`

## 6. Prompt strategy (summary)

- **Reply prompt** = role ("You ARE {name}") + persona card + style stats as hard constraints
  + emoji/delivery rules + 8–15 retrieved real pairs + 3–5 memories + user mood + session turns.
- The LLM writes like the person **with emojis**; it does *not* write Fish cues. Cues are derived
  deterministically from emojis/markers via the persona's emoji map (`speech/cues.py`).
  Exception: optional "director" pass when a reply has no emotional markers but context calls for one.
- Post-checks: length vs. style stats (regenerate/trim if > p90), output guard, placeholder leak check.

## 7. Configuration (additions to `Settings` / `.env.example`)

```
# LLM — Gemini on Vertex AI, auth via gcloud ADC (no key) — see agents/knowledge/vertex-gemini.md
GCP_PROJECT=eseller-ai
GCP_LOCATION=global
LLM_CHAT_MODEL=gemini-3.5-flash-lite        # live replies + mood (~1 s)
LLM_CHAT_THINKING=low
LLM_BUILD_MODEL=gemini-4-argon              # persona card, emoji map, baseline (offline)
LLM_CLASSIFY_MODEL=gemini-3.5-flash-lite    # guardrail topic windows
# Embeddings / retrieval
EMBEDDING_MODEL=gemini-embedding-2
VECTOR_STORE_DIR=data/vectors
RETRIEVAL_PAIRS_K=12
RETRIEVAL_MEMORIES_K=4
# Fish Audio
FISH_AUDIO_API_KEY=            (exists)
FISH_TTS_MODEL=s2.1-pro
FISH_TTS_FORMAT=mp3
# Data / guardrails
DATA_DIR=data
GUARD_REVIEW_MODE=true
GUARD_TOPIC_WINDOW=20
GUARD_NER_MIN_SCORE=0.6
```

## 8. Dependencies (planned)

| Purpose | Package |
|---|---|
| Fish Audio | `fish-audio-sdk` (or plain `httpx` against REST) |
| LLM + embeddings | `google-genai` (Vertex AI mode, ADC) behind `app/llm/client.py` |
| Emoji | `emoji` |
| PII / NER | `presidio-analyzer` (+ spaCy model; GLiNER optional) |
| Vector store | `chromadb` (proposed) |
| Uploads | `python-multipart` |

Add each only when the milestone that needs it starts.

## 9. Testing

- Unit tests per module with synthetic fixtures in `tests/fixtures/` (fake names, fake numbers that
  pass format checks, e.g. Luhn-valid test card numbers).
- LLM and Fish clients mocked via dependency overrides; one opt-in live smoke test marked `@pytest.mark.live`.
- Privacy regression test: run full ingest on fixture → assert no PII patterns anywhere under the persona dir.
