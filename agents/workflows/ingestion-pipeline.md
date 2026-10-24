# Ingestion pipeline (M1) — `app/ingest/`, `app/guardrails/`

Spec: `docs/requirements/privacy-and-guardrails.md`. Requirements: FR-ING-*, FR-GRD-*.

## Flow

```
POST /personas/{id}/ingest (file, rules)
  └─ save upload to tempfile.TemporaryDirectory()      # deleted in finally
     ├─ .zip → extract only *.txt (and *.opus list for FR-VOICE-03, not read yet)
     ├─ parse_whatsapp(text) -> list[Message]
     ├─ participants = sorted({m.sender}) ; confirm export_name ∈ participants
     ├─ sanitize_chat(messages, persona, rules) -> (clean, report)
     │    1 drop_artifacts   2 apply_rules   3 redact_pii   4 pseudonymize   5 topic_filter
     ├─ write messages.jsonl, report.json, review.jsonl, pseudonyms.json
     └─ persona.status = "ingested"
```

## Parser notes (`whatsapp.py`)

- Android: `DD/MM/YY, H:MM am - Name: text` (also `pm`, 24h `HH:MM`, sometimes narrow no-break space ` ` before am/pm).
- iOS: `[DD/MM/YY, H:MM:SS AM] Name: text`; lines may start with U+200E (LRM) — strip it.
- Date order may be D/M or M/D depending on phone locale: detect by scanning for a field > 12.
- A line not matching the header regex continues the previous message (multi-line).
- System lines have no `Name:` part → treat as artifact.
- Export of a group chat has many senders; only the persona's replies become pairs, but all senders' text is context.

## Artifact strings to drop (English exports; extend as found)

`<Media omitted>`, `image omitted`, `video omitted`, `audio omitted`, `sticker omitted`,
`This message was deleted`, `You deleted this message`, `Messages and calls are end-to-end encrypted`,
`<This message was edited>` (strip the suffix, keep text), `Missed voice call`, `null`.

## PII

- Run UPI before EMAIL (UPI ids look like emails). Run CARD with Luhn before PHONE/AADHAAR.
- Placeholders are typed (`[PHONE]`), not removed, to keep sentence shape.

## Pseudonymization

- Keep set = {persona export_name, operator_name, their first names}.
- Exact-match other participants' names first (from the participant list), then NER.
- Map is case-insensitive and stable across re-ingests (load existing `pseudonyms.json`).

## Topic classifier

- Windows of `GUARD_TOPIC_WINDOW` (20) messages, stride = window (no overlap) for cost.
- Input is post-step-4 text only. JSON schema enforced; on parse failure → treat as review.
- `confidence < 0.6` and review mode → `review.jsonl`, excluded from build until approved.

## Tests to keep green

- Parser: Android, iOS, multi-line, LRM, D/M vs M/D, system lines.
- PII: each label positive + negative (e.g. 12-digit non-Aadhaar starting with 0/1, non-Luhn 16 digits).
- Privacy regression: fixture → full ingest → regex scan all files under persona dir = 0 hits.
- Temp dir removed even when parsing raises.
