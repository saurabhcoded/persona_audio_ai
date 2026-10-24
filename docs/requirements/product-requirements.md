# Product Requirements — Persona Voice

Status: Draft v0.1 · 2026-10-24

## 1. Problem & vision

Generic chatbots sound generic. Text-to-speech sounds flat. The goal is a chatbot that, given a
person's chat history (and optionally their voice notes), responds **with that person's essence**:

- **What they'd say**: their opinions, memories, the way they react to situations.
- **How they'd write it**: language mix (e.g. Hinglish), slang, spelling quirks, message length, emojis.
- **How they'd sound**: their cloned voice, with expressive delivery (laughing, sighing, softening)
  matching *their* emotional habits, not generic ones.

## 2. Users

| User | Need |
|---|---|
| **Operator** (the person setting up a persona) | Import a chat export, review what gets stored, build a persona, add a voice, chat with it. |
| **Chat user** (often the same person) | Talk to the persona in text, hear replies in the persona's voice. |

MVP is single-operator, self-hosted. No multi-tenant accounts.

## 3. Scope

### In scope (MVP)
- WhatsApp `.txt` / `.zip` chat export import (Android + iOS formats).
- Privacy guardrail that sanitizes chats **before** anything is stored, embedded or sent to an LLM.
- Persona building: persona card, per-person emoji→emotion map, retrievable real reply examples, knowledge base.
- Chat endpoint that replies in-persona, grounded in retrieved examples and memories.
- Conversion of the reply's emojis/emotions into Fish Audio S2 expression cues.
- Voice from Fish Audio: either an existing voice model or a clone from the persona's voice notes.
- React chat UI with audio playback and an ingestion/review screen.
- Evaluation tooling (blind real-vs-generated test set).

### Out of scope (MVP)
- Fine-tuning a model (kept as a later option, see M8).
- Telegram/WeChat/Instagram imports (parser interface should allow adding them).
- Realtime phone/voice-call mode and speech-to-text input (later).
- Multi-user accounts, billing, public hosting.
- Video avatars.

## 4. Functional requirements

Priority: **M** = must (MVP), **S** = should, **C** = could.

### 4.1 Persona & consent (FR-PER)
| ID | Requirement | P |
|---|---|---|
| FR-PER-01 | Operator can create a persona with display name, the persona's name as it appears in the export, and the operator's own name in the export. | M |
| FR-PER-02 | Persona creation requires a **consent attestation** (persona consented, or operator has a lawful right, e.g. memorial by family). Stored with timestamp. Voice cloning is blocked without it. | M |
| FR-PER-03 | Operator can view persona status (ingested, sanitized, built, voice ready). | M |
| FR-PER-04 | Operator can **fully erase** a persona (all derived data, embeddings, voice references). | M |
| FR-PER-05 | Multiple personas can coexist; each is isolated (no cross-persona retrieval). | S |

### 4.2 Ingestion (FR-ING)
| ID | Requirement | P |
|---|---|---|
| FR-ING-01 | Upload WhatsApp export as `.txt` or `.zip` (zip may include media; media is ignored except voice notes, see FR-VOICE-03). | M |
| FR-ING-02 | Parse both Android (`12/03/24, 9:41 pm - Name: text`) and iOS (`[12/03/24, 9:41:05 PM] Name: text`) formats, 12h/24h, multi-line messages. | M |
| FR-ING-03 | Detect participants and let the operator confirm which one is the persona. | M |
| FR-ING-04 | Raw export is processed in memory/temp and **deleted after sanitization**; never persisted. | M |
| FR-ING-05 | Merge consecutive messages from the same sender into a "burst" while keeping per-message boundaries for style stats. | M |
| FR-ING-06 | Re-ingesting additional exports appends to the persona (dedup by timestamp+sender+hash). | S |

### 4.3 Privacy guardrail (FR-GRD) — detail in [privacy-and-guardrails.md](privacy-and-guardrails.md)
| ID | Requirement | P |
|---|---|---|
| FR-GRD-01 | Strip WhatsApp artifacts (`<Media omitted>`, deleted messages, system/encryption notices). | M |
| FR-GRD-02 | Redact PII locally with placeholders: phone, email, Aadhaar, PAN, card (Luhn), UPI, IFSC, OTP, passwords/secrets, URLs. | M |
| FR-GRD-03 | Pseudonymize third-party names/places consistently (same real name → same pseudonym); persona + operator names kept. | M |
| FR-GRD-04 | Classify message windows for sensitive topics → KEEP / REDACT / DROP, on already-redacted text only. | M |
| FR-GRD-05 | Operator rules: exclude contacts, keywords, date ranges. | M |
| FR-GRD-06 | Review queue for low-confidence windows; operator approves/rejects before build. | S |
| FR-GRD-07 | Sanitization report (counts by category, dropped/redacted windows) — no raw text in the report. | M |
| FR-GRD-08 | Output guard: every generated reply is PII-scanned before display/TTS; on hit → strip or regenerate. | M |

### 4.4 Persona building (FR-BLD)
| ID | Requirement | P |
|---|---|---|
| FR-BLD-01 | Build **reply pairs** (preceding context → persona's reply) from sanitized chat and index them for similarity retrieval. | M |
| FR-BLD-02 | Extract a **persona card** from the persona's own messages: language mix, quirks, length, catchphrases, nicknames, humor, reactions per emotion, opinions, key facts/people (pseudonymized), "never says" list. | M |
| FR-BLD-03 | Compute **style stats** deterministically: avg/median message length, burst size, emoji rate, casing, punctuation habits, top tokens/phrases. | M |
| FR-BLD-04 | Build a **memory/knowledge base** of facts and events (chunked sanitized windows + extracted facts) for retrieval. | M |
| FR-BLD-05 | Build the persona's **emoji map** (see FR-EMO-01). | M |
| FR-BLD-06 | Persona card is viewable and editable by the operator (manual corrections win). | S |

### 4.5 Emoji & emotion (FR-EMO)
| ID | Requirement | P |
|---|---|---|
| FR-EMO-01 | For each emoji the persona uses ≥5 times, infer its **person-specific meaning** from context → `{meaning, fish_cue, spoken_as}`. | M |
| FR-EMO-02 | Derive the persona's **emotional baseline** (distribution of emotions in their messages) and delivery rules (e.g. "teasing → [chuckling], never [angry]"). | M |
| FR-EMO-03 | Map text markers (`hahaha`, `hmm…`, ALL CAPS, elongated words) to cues. | S |
| FR-EMO-04 | Detect the **chat user's mood** from their message (text + emojis) and pass it to the reply generator. | M |

### 4.6 Chat (FR-CHAT)
| ID | Requirement | P |
|---|---|---|
| FR-CHAT-01 | `POST /chat` returns an in-persona reply for a session (persona_id, session_id, message). | M |
| FR-CHAT-02 | Prompt includes: persona card, emoji/delivery rules, top-k retrieved real reply pairs, top-k memories, user mood, recent session turns. | M |
| FR-CHAT-03 | Reply matches persona style: language mix, length, emojis; may be split into multiple bubbles like the persona's bursts. | M |
| FR-CHAT-04 | Persona must not invent sensitive facts or reveal placeholders/pseudonyms awkwardly (e.g. never says "[PHONE]"). | M |
| FR-CHAT-05 | Session memory: recent turns kept verbatim; older turns rolled into a short session summary. | S |
| FR-CHAT-06 | LLM provider is pluggable behind one interface. | M |

### 4.7 Expressive speech (FR-TTS)
| ID | Requirement | P |
|---|---|---|
| FR-TTS-01 | Reply has two renditions: **display text** (emojis kept, no cues) and **TTS text** (emojis → Fish `[cues]`, cues validated). | M |
| FR-TTS-02 | Emoji conversion: dominant emoji's cue placed at **sentence start**; repetition (≥3) raises intensity; emoji-only messages use `spoken_as`. | M |
| FR-TTS-03 | Cue validator: bracket syntax only (convert `(x)`), ≤3 cues per sentence, sentence-level emotion at sentence start, sound effects followed by matching text. | M |
| FR-TTS-04 | Synthesize with Fish Audio `s2.1-pro` (model configurable), persona's voice, mp3 by default. | M |
| FR-TTS-05 | `speak=false` returns text only (no TTS cost). | M |
| FR-TTS-06 | Streaming: sentence-chunked TTS over websocket for lower latency. | C |

### 4.8 Voice (FR-VOICE)
| ID | Requirement | P |
|---|---|---|
| FR-VOICE-01 | Attach an existing Fish Audio voice model ID to a persona. | M |
| FR-VOICE-02 | Upload clean voice clips (+ transcript) for instant cloning via `references`. | M |
| FR-VOICE-03 | Optionally extract voice notes (`.opus`) from the WhatsApp zip as clone candidates; operator picks clips. | C |
| FR-VOICE-04 | Create a persistent Fish voice model from clips. | S |

### 4.9 UI (FR-UI)
| ID | Requirement | P |
|---|---|---|
| FR-UI-01 | Persona list + create (with consent checkbox and explanation). | M |
| FR-UI-02 | Ingest screen: upload, choose persona participant, set exclusion rules, view sanitization report. | M |
| FR-UI-03 | Review queue screen (approve/reject flagged windows; shows redacted text only). | S |
| FR-UI-04 | Chat screen: bubbles in persona style, play/auto-play audio per reply, toggle voice. | M |
| FR-UI-05 | Persona card viewer/editor. | S |
| FR-UI-06 | Debug panel (dev only): retrieved examples, mood, TTS text with cues. | S |

### 4.10 Evaluation (FR-EVAL)
| ID | Requirement | P |
|---|---|---|
| FR-EVAL-01 | Hold out ~5% of reply pairs from the index as a test set. | M |
| FR-EVAL-02 | Generate replies for held-out contexts; export a shuffled blind real-vs-generated sheet for human judging. | M |
| FR-EVAL-03 | Automatic style metrics vs. real: length distribution, emoji rate, language-mix ratio. | S |

## 5. Non-functional requirements

| ID | Requirement |
|---|---|
| NFR-01 Privacy | No raw chat persisted; no message text in logs (log ids/counts only); PII never sent to external APIs before local redaction; `data/` is git-ignored. |
| NFR-02 Latency | Text reply p50 ≤ 4 s; reply + full audio p50 ≤ 8 s (non-streaming) on a normal connection. |
| NFR-03 Cost | `speak=false` path makes no TTS call; classification uses a cheap model; reply pairs/persona card cached, not rebuilt per request. |
| NFR-04 Scale | Handle an export of 100k messages: ingestion ≤ 15 min, chat retrieval ≤ 300 ms. |
| NFR-05 Portability | Runs locally and in the existing Docker setup; no GPU required. |
| NFR-06 Configurability | All keys, model names, thresholds in `Settings` + `.env.example`. |
| NFR-07 Testability | Every pipeline stage unit-testable with synthetic fixtures; external APIs mocked in tests. |
| NFR-08 Languages | English and Hinglish (romanized Hindi) first-class; Fish cues work in 13 languages incl. English. |

## 6. Acceptance criteria (MVP)

1. Uploading a sample WhatsApp export produces a sanitization report; a grep of `data/` finds no
   phone numbers, emails, Aadhaar, PAN or card numbers from the fixture.
2. Building the persona produces a persona card, emoji map, and a reply-pair index.
3. `POST /chat` returns display text + TTS text with valid Fish cues + audio in the persona's voice.
4. Emoji-only replies (e.g. "😂😂") are spoken (e.g. "[laughing] hahaha"), not silent.
5. Blind test: judges who know the persona misidentify ≥ 30% of generated replies as real (target, not gate).
6. Deleting a persona removes every file under its data directory and its vector collection.

## 7. Milestones

| M | Deliverable |
|---|---|
| M0 | Requirements docs + `agents/` steering (this) |
| M1 | WhatsApp parser + guardrail pipeline + `/personas`, `/ingest` endpoints + tests |
| M2 | Persona build: style stats, persona card, emoji map, reply-pair + memory index |
| M3 | `/chat` text-only, LLM abstraction, output guard |
| M4 | Expressive TTS: emoji→cue converter, cue validator, Fish TTS, voice attach/clone |
| M5 | Frontend: personas, ingest/report, chat with audio |
| M6 | Evaluation harness + review queue + persona card editor |
| M7 | Streaming TTS (websocket, sentence chunks) |
| M8 | Optional LoRA fine-tune path for higher style fidelity |

## 8. Risks

| Risk | Mitigation |
|---|---|
| Impersonation / misuse of a real person's identity and voice | Consent attestation required; local/self-hosted; no public sharing features. |
| Sensitive data leaking into KB or replies | Layered guardrail + output guard + no-raw-storage rule. |
| Persona sounds too polite / too long ("assistant voice") | Real reply exemplars, style stats as hard constraints, "never says" list, length post-check. |
| Hinglish name detection misses | Participant-list exact matching + operator name list + GLiNER/Presidio. |
| Cue overuse sounds theatrical | Validator caps cues; cues come from persona's own emoji/emotion habits. |
| Fish S1 deprecation (2026-12-31) | Use S2 bracket syntax only; never parentheses. |

## 9. Open questions

- ~~OQ-1 LLM provider~~ → resolved: Gemini on Vertex AI (flash-lite for chat, argon for offline build); see `agents/decisions.md` D-008.
- **OQ-2** Vector store (Chroma proposed, local persistent).
- **OQ-3** Sensitive-topic classification: external LLM on redacted text vs. local Llama Guard.
- **OQ-4** Is there real voice-note material for cloning, and how much?
