# Fish Audio reference (verified 2026-10-24 from docs.fish.audio)

Sources: https://docs.fish.audio/overview/capabilities ·
https://docs.fish.audio/developer-guide/core-features/emotions.md ·
https://docs.fish.audio/features/text-to-speech.md ·
https://docs.fish.audio/features/text-to-speech/drama-3.md

## Models

| Model | Notes |
|---|---|
| `s2.1-pro` | Recommended production TTS. **Default/fallback** when `model` header is missing or misspelled (silent fallback — no error). |
| `s2-pro` | Natural-language expression control, multi-speaker. Python SDK default. |
| `drama-3` | Voice direction / content creation; paired word-level tags. |
| `s1` | **Deprecated**, retires 2026-12-31 → served by `s2.1-pro`. Parentheses cues NOT auto-converted. |
| `transcribe-1-pro` | Speech-to-text, multi-speaker, emits inline emotion cues. |

## S2 expression syntax (what we generate)

- Square brackets, free-form natural language: `[happy] What a beautiful day!`, `What a [warm and happy] day!`
- Stack: `[sad][whispering]`. Intensity: `[slightly sad]`, `[very excited]`, `[extremely angry]`.
- **Sentence-level emotion at the start of the sentence.** Tones & sound effects anywhere.
- `[emphasis]` directly before the stressed word.
- Sound effects need matching text: `[laughing] ha ha`.
- Max ~3 combined emotions per sentence; one primary emotion recommended.
- Cues don't count toward token limits, add no latency. 13 languages incl. English.

Recommended vocabulary:
- **Basic emotions:** happy, sad, angry, excited, calm, nervous, confident, surprised, satisfied,
  delighted, scared, worried, upset, frustrated, depressed, empathetic, embarrassed, disgusted, moved,
  proud, relaxed, grateful, curious, sarcastic.
- **Advanced:** disdainful, unhappy, anxious, hysterical, indifferent, uncertain, doubtful, confused,
  disappointed, regretful, guilty, ashamed, jealous, envious, hopeful, optimistic, pessimistic,
  nostalgic, lonely, bored, contemptuous, sympathetic, compassionate, determined, resigned.
- **Tones:** in a hurry tone, shouting, screaming, whispering, soft tone, emphasis.
- **Sound effects:** laughing, chuckling, sobbing, crying loudly, sighing, groaning, panting, gasping,
  yawning, snoring, clear throat.
- **Special:** audience laughing, background laughter, crowd laughing.
- **Pauses:** break, long-break.

Pitfalls: missing brackets, overusing tags in short text, conflicting emotions, long descriptions,
cue far from its sentence, sound effect without supporting text.

## drama-3 extras (not used in MVP)

Paired tags `<whisper>…</whisper>`, `<emphasis>`, `<soft>`, `<fast>`, `<slow>`, `<stress>`,
`<forceful>`; language tags `<french>…`; phonemes `<|phoneme_start|>…<|phoneme_end|>`;
multi-speaker `<|speaker:0|>` with `reference_id` array.

## API / SDK

- Request fields: `text`, `reference_id`, `references` (audio + transcript, instant clone), `format`
  (mp3 default | wav | pcm | opus), `mp3_bitrate` (64/128/192), `sample_rate`, `latency`
  (balanced default | normal), `chunk_length` 100–300 (200), `prosody` {speed 0.5–2.0, volume},
  `temperature`, `top_p`, `repetition_penalty`, `max_new_tokens`, `normalize`, `language` (BCP-47,
  normalization/timestamps only — doesn't change voice). Model via `model` header.
- Python SDK:
  ```python
  from fishaudio import FishAudio
  from fishaudio.types import TTSConfig, Prosody, ReferenceAudio
  client = FishAudio()                       # env FISH_API_KEY; we pass api key from settings
  audio = client.tts.convert(text=..., reference_id=..., config=TTSConfig(temperature=0.7, top_p=0.7))
  ```
  `tts.convert()` → bytes · `tts.stream()` → iterable · `tts.stream_websocket()` → realtime text in.
- **Verified with fish-audio-sdk 1.3.0:** `AsyncFishAudio(api_key=...)`; `await client.tts.convert(text=, reference_id=, format=, model=)` → bytes.
  The SDK's `model` type hint lists only `speech-1.5/1.6, s1, s2-pro`, but `model="s2.1-pro"` works at runtime
  (passed as header) — hence the `# type: ignore` in `app/speech/tts.py`.
- Without `reference_id` Fish uses a default voice (works; good for the demo). ~2.5 s for one sentence, ~3.9 s for 4 lines, mp3 128 kbps mono 44.1 kHz.
- Verify exact SDK constructor/model params against https://docs.fish.audio/api-reference/sdk/python/resources.md before coding.

## Voice catalog (app/speech/voices.py, verified 2026-10-24 with s2.1-pro)

| Name | id | Notes |
|---|---|---|
| Sarah (F, en) | 933563129e564b19a115bedd57b7406a | young, conversational, soft |
| Selene (F, en) | b347db033a6549378b48d00acb0d06cd | calm, gentle |
| Slax (M, en) | c5f56a6cc2ec4fa8920cb4c5889a3fb7 | clear, smooth |
| Verity (M, en) | 711cf3ed00ab441a8f54a45058047b7a | young, conversational |
| Girl Hindi (F, hi) | 4d7609058bd34213b1378b29efbde1f1 | user-provided; Fish title "Girl hindi" |
| Boy Hindi (M, hi) | 528f686ef2154885b368dd4b93fb8728 | user-provided; Fish title "Gojo hindi" |

- Defaults picked from `voices.list(tags=male|female, language=en, sort_by=task_count)`, skipping
  celebrity/character imitations (announcers, YouTubers) that top the popularity list.
- **Concurrency limit:** 6 parallel TTS calls → one `HTTP 429 … exceeded your current concurrency limit`
  (`fishaudio.exceptions.RateLimitError`). `TTSClient.synthesize` retries 429 twice with backoff.
- Each voice ≈ 1.5–2 s for a short Hinglish line from a cold call; inside a streamed reply, line audio
  arrived 0.25–0.6 s after the line was written (Boy Hindi, 3-line replies).

## Voice cloning

Instant: pass `references` (clean clip + transcript) per request. Persistent: create a voice model
from clips, use its `reference_id`. Clips should cover multiple moods so cues have range to draw on.
Requires rights to the voice.
