# Persona build (M2) — `app/persona/`, `app/retrieval/`

Requirements: FR-BLD-*, FR-EMO-01..03, FR-EVAL-01. Input: sanitized `messages.jsonl` only.

## Steps (`POST /personas/{id}/build`)

1. **Bursts** — merge consecutive messages from the same sender within 2 min into a burst.
2. **Style stats** (`stats.py`, deterministic) — per persona message & burst:
   length p50/p90 (chars, words), msgs per burst, emoji rate, top emojis, % lowercase-start,
   punctuation habits (`...`, `!!`, no full stops), elongations (`okayyy`), top n-grams, language-mix
   estimate (romanized Hindi token list vs English).
3. **Reply pairs** (`pairs.py`) — for each persona burst, context = previous ≤4 messages from others
   (same day, within 6 h). Mark ~5% random as `holdout` (fixed seed) — not indexed (FR-EVAL-01).
4. **Index** — embed `context` (not reply) for pairs; store reply + metadata. Separate `memories`
   collection: windows of ~15 messages embedded as-is.
5. **Persona card** (`card.py`) — LLM over persona's messages in batches (map), then merge (reduce)
   into the schema: language_mix, quirks, length, catchphrases (quoted), nicknames, humor, reactions
   {happy, annoyed, sad, other_is_upset}, opinions, key_people (pseudonyms), key_facts, never_says,
   delivery_rules.
6. **Emoji map** (`emoji_map.py`) — emojis used ≥5 times; ≤15 contexts each (prev message + persona
   message) → LLM → `{meaning, fish_cue, spoken_as}`. Validate `fish_cue` is bracketed and short.
7. **Emotional baseline** — LLM labels a sample (~300) of persona messages with one emotion from the
   Fish recommended list → distribution stored in the card.
8. status → `built`.

## Notes

- Operator edits to the card (`PUT /card`) are stored as overrides and re-applied after rebuilds.
- Rebuild is idempotent; vector collections are dropped and recreated.
- Cache LLM outputs per input hash to keep rebuilds cheap.
