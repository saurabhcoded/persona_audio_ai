# Privacy & Guardrails — Persona Voice

Status: Draft v0.1 · 2026-10-24

## 1. Principles

1. **Consent first.** A persona is a real person. Creation requires a consent attestation; voice
   cloning is blocked without it (FR-PER-02). Fish Audio's terms require rights to the cloned voice.
2. **Sanitize before anything else.** Nothing is embedded, stored, or sent to an external API
   before local redaction (steps 1–3 below).
3. **Raw data is ephemeral.** Uploaded exports live only in memory / a temp dir and are deleted after
   sanitization, including on failure.
4. **Keep style, drop facts.** Placeholders (`[PHONE]`, `Person_3`) preserve sentence shape, tone and
   emojis so style learning still works.
5. **Defense in depth.** Input sanitization + output guard. Neither alone is trusted.
6. **Right to erase.** Deleting a persona removes all derived data (FR-PER-04).

## 2. Data classification

| Data | Stored? | Leaves machine? |
|---|---|---|
| Raw export | No (temp only) | Never |
| Sanitized messages | Yes, `data/personas/<id>/` | Yes, to LLM/embedding APIs |
| Pseudonym map (real→fake) | Yes, local only | Never (not in prompts, UI, logs) |
| Persona card / emoji map | Yes | In prompts |
| Voice clips | Yes, local | To Fish Audio (for cloning/TTS) |
| Logs | Yes | — Only ids, counts, timings; **never message text** |
| Saved places (home address…) | Yes, `DATA_DIR/places.json` | To Google Places/Routes only to plan a route; **never to the LLM** (it sees the label "home") |

## 3. Sanitization pipeline (`app/guardrails/pipeline.py`)

Order matters: local steps run first so external services only ever see redacted text.

| # | Stage | Where | Action |
|---|---|---|---|
| 1 | Artifacts | local | Drop `<Media omitted>`, `This message was deleted`, `Messages and calls are end-to-end encrypted…`, joins/leaves, missed calls. |
| 2 | Operator rules | local | Drop messages/windows from excluded contacts, containing excluded keywords, or within excluded date ranges. |
| 3 | PII regex | local | Replace with typed placeholders (table below). |
| 4 | Pseudonymize | local | Third-party PERSON/LOCATION → consistent `Person_N` / `Place_N`. Participant names from the export header matched exactly first; NER (Presidio, optional GLiNER) second, score ≥ `GUARD_NER_MIN_SCORE`. Persona and operator names kept. |
| 5 | Topic classifier | LLM (cheap model) or local Llama Guard | Windows of `GUARD_TOPIC_WINDOW` messages → `KEEP` / `REDACT` (spans → `[PRIVATE]`) / `DROP`. Low confidence → review queue when `GUARD_REVIEW_MODE`. |
| 6 | Report | local | `SanitizationReport` — counts only. |

### 3.1 PII placeholders

| Label | Pattern notes |
|---|---|
| `[EMAIL]` | standard email |
| `[UPI]` | `handle@okaxis/ybl/paytm/upi/apl/ibl/axl/sbi…` — checked **before** email |
| `[PHONE]` | Indian mobile `(+91)?[6-9]\d{9}` with separators; international `+<cc>…` |
| `[AADHAAR]` | exactly 12 digits (not part of a longer run), first 2–9, optional spaces in 4-4-4 |
| `[PAN]` | `[A-Z]{5}\d{4}[A-Z]` |
| `[IFSC]` | `[A-Z]{4}0[A-Z0-9]{6}` |
| `[CARD]` | 13–19 digits with separators **and** Luhn-valid |
| `[ACCOUNT]` | any remaining 9–18 digit run (bank accounts, non-Luhn card-like numbers) |
| `[OTP]` | "otp/code/pin" near a 4–8 digit number |
| `[SECRET]` | "password/pwd/pin is …" value |
| `[URL]` | http(s) links |

### 3.2 Topic policy

**DROP** window if mainly about: sexual/intimate content; anyone's medical or mental-health condition;
abuse, self-harm; legal trouble; specific finances (debts, salary, account balances); secrets
explicitly shared in confidence ("don't tell anyone"); third parties' private matters.

**REDACT** spans when only a line or two is sensitive. Prefer REDACT over DROP when the rest is
normal banter (style value).

**KEEP** casual talk, jokes, plans, opinions, everyday life.

Classifier returns JSON `{action, categories[], redact_spans[], confidence}`. Log the decision
(window id, action, categories) — never the text.

## 4. Output guard (`app/guardrails/output.py`)

Every reply, before display or TTS:
1. Run the PII regex set → if any hit, strip it and regenerate once; if it still fails, return the stripped text.
2. Placeholder leak check: reply must not contain `[PHONE]`, `[PRIVATE]`, `Person_N` style tokens
   verbatim — rephrase (e.g. "her" / "that guy") via a regenerate instruction.
3. Never output pseudonym-map contents.

## 5. Tools used

- **Presidio** (local NER + India recognizers: `IN_AADHAAR`, `IN_PAN`, …) for stage 4, custom regex for UPI/IFSC.
- **LLM Guard** / **Llama Guard** are candidates for stages 5 and the output guard (OQ-3).
- Custom code is still required for WhatsApp artifacts and chat-specific judgments ("secret in confidence").

## 6. Repository rules

- `data/`, uploads, voice clips, and any real export are git-ignored. Never commit them.
- Tests use **synthetic** fixtures only. No real chats in tests, docs, prompts or issues.
- Don't paste real chat content into the agent conversation for debugging; use the report and ids.

## 7. Compliance notes

Processing a third party's personal data falls under India's DPDP Act 2023 (consent, purpose
limitation, erasure). The consent attestation, purpose-limited local processing, and full-erase
endpoint are the MVP controls. This is not legal advice; review before any shared/hosted deployment.
