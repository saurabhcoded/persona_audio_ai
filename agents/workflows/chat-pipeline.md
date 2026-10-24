# Chat + expressive speech (M3, M4) — `app/chat/`, `app/llm/`, `app/speech/`

Requirements: FR-CHAT-*, FR-TTS-*, FR-VOICE-*, FR-EMO-04, FR-GRD-08.

## Request flow (`POST /chat`)

```
1 load persona (409 if not built; if speak=true and no voice → 409)
2 mood = detect_mood(message)                      # cheap LLM or heuristic on text+emojis
3 pairs = store.search(persona, "pairs", message + last turn, k=RETRIEVAL_PAIRS_K)
  mems  = store.search(persona, "memories", message, k=RETRIEVAL_MEMORIES_K)
4 prompt = prompts.reply(card, stats, emoji_map rules, pairs, mems, mood, session turns)
5 reply = llm.complete(prompt)                     # plain persona text WITH emojis, bursts split by newline
6 post-checks: output guard (PII, placeholder leak) → length vs stats p90 → regenerate once if failing
7 bubbles = reply.split("\n")                      # display text
8 if speak: tts_text = validate(emojis_to_cues(reply, emoji_map)); audio = tts(tts_text, voice)
9 session.append(user, reply); roll summary if > N turns
```

## Prompt rules (reply)

- "You ARE {name}" — never "an AI imitating". No assistant phrasing; respect `never_says`.
- Pairs shown as real examples: `Them: …\n{name}: …`. Instruct: match their length/language/emojis.
- Pseudonyms in context: instruct to refer to people naturally and never output placeholders.
- Output only the message(s); multiple bubbles separated by newline if the persona bursts.

## Short forms before cues

- Spoken text per line = `emojis_to_cues(expand_shortforms(guard_reply(line)))` when the persona's
  `expand_shortforms_in_speech` is on (D-024). Expansion runs before cue conversion so cue words are never
  touched and laugh-text detection sees the expanded words. Display bubbles are expanded only with
  `expand_shortforms_in_text`.

## Emoji → cue (`speech/cues.py`)

- Split into sentences; per sentence: find emojis, pick dominant; cue from persona emoji map
  (fallback to default map); remove emojis from text.
- Cue goes at **sentence start**. Repeated ≥3 → intensity ("[very …]").
- Emoji-only sentence → `{cue} {spoken_as}`.
- **Single laugh emoji next to text → `[joking] text`** (no inserted "hahaha"), user preference (D-018).
  Laugh = cue in `LAUGH_CUES` (laughing / laughing loudly / chuckling), so persona maps count too.
  Two or more laugh emojis, or a lone laugh emoji, still voice a real laugh.
- Text markers: `haha+`/`hehe` → ensure a `[laughing]`/`[chuckling]` cue before it; `hmm+` → `[break]` after.
- `strip_cues(text)` for anything shown in UI.

## Cue validator

- Convert `(emotion)` → `[emotion]` (S1 → S2).
- Max 3 cues per sentence; drop extras from the end.
- Sound-effect cues (`laughing`, `chuckling`, `sighing`, …) need following text; if none, add `spoken_as` or drop.
- Cue text ≤ 40 chars, no nested brackets.

## TTS (`speech/tts.py`)

- Fish model from `FISH_TTS_MODEL` (default `s2.1-pro`), format mp3.
- Voice: `reference_id` (persistent model) or `references=[ReferenceAudio(audio, text)]` (instant clone).
- Pass the API key from `settings.fish_audio_api_key` explicitly (SDK default env var is `FISH_API_KEY`).
- SDK is sync → call in threadpool from async routes.
- Streaming: first line its own clip, later lines merged (D-016, D-026) via `app/chat/speaker.py`; the browser
  trims, levels and gaplessly schedules clips (`frontend/src/audioQueue.js`). Fish websocket streaming only if
  replies get long.
