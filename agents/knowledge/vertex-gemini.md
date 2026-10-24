# Vertex AI / Gemini reference (verified 2026-10-24)

## Access

- Auth: gcloud **Application Default Credentials** (`gcloud auth application-default login`, already done).
  No API key in `.env`.
- Project `eseller-ai` (gcloud default), Vertex AI ("Agent Platform API") enabled.
- Use location **`global`** (endpoint `aiplatform.googleapis.com`). gcloud's default region is
  `asia-south1`, but newer models are served from `global`; don't reuse the compute region.
- SDK: `google-genai`
  ```python
  from google import genai
  from google.genai import types
  client = genai.Client(vertexai=True, project=settings.gcp_project, location=settings.gcp_location)
  resp = client.models.generate_content(
      model="gemini-3.5-flash-lite",
      contents=prompt,
      config=types.GenerateContentConfig(
          system_instruction=system, temperature=0.9, max_output_tokens=300,
          thinking_config=types.ThinkingConfig(thinking_level="low"),
      ),
  )
  ```
  Async: `client.aio.models.generate_content(...)`. JSON: `response_mime_type="application/json"` + `response_schema`.
- In Docker, ADC isn't present: mount `~/.config/gcloud` read-only or use a service-account key
  via `GOOGLE_APPLICATION_CREDENTIALS` (never commit it).

## Available Gemini models in this project (publisher list, 2026-10-24)

gemini-4-argon · gemini-3.8/3.7/3.6/3.5-flash · gemini-3.5-flash-lite · gemini-3.1-flash-lite ·
gemini-3.1-pro-preview · gemini-2.5-pro/flash/flash-lite · gemini-embedding-2 · TTS/live/transcribe variants.

## Benchmark — short Hinglish persona reply, 200 max tokens, global endpoint

| Model | Config | Latency | Notes |
|---|---|---|---|
| gemini-3.5-flash-lite | thinking low | 0.9–1.2 s | Good style; **chosen for live chat** |
| gemini-3.5-flash-lite | default | 1.3–1.6 s | Sometimes longer single line |
| gemini-3.1-flash-lite | default | 1.4–1.5 s | Good |
| gemini-4-argon | default / low | 3.1–6.3 s | Most in-character (short teasing bursts); **chosen for offline build** |
| gemini-3.8-flash | default | >8 s, timed out | Avoid for chat |

## Gotchas

- `gemini-4-argon`: `thinkingLevel: minimal` → 400 "unsupported"; `thinkingBudget` → 400 "not supported,
  use thinking level". Use `thinking_level="low"` (or omit).
- `gemini-3.5-flash-lite` accepts `thinkingLevel` minimal/low and `thinkingBudget: 0`.
- Few-shot prompts in `Them:/Name:` form make models echo the `Name:` prefix — strip a leading
  `"{name}:"` from each output line in post-processing.
- Model returns bursts as newline-separated lines naturally when examples show bursts → use as bubbles.
