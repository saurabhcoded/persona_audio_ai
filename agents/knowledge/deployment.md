# Deployment — Google Cloud Run (set up 2026-10-24)

Live: **https://persona-voice-627395208842.asia-south1.run.app** (project `eseller-ai`, region `asia-south1`).
Redeploy: `make deploy` (Cloud Build builds the Dockerfile `prod` stage from source; `.gcloudignore`
keeps `.env`, `data/`, `.venv`, `node_modules` out of the upload). Logs: `make deploy-logs`.

## Resources (created with user approval)

| Resource | Name | Purpose |
|---|---|---|
| Cloud Run service | `persona-voice` | FastAPI + built SPA, port from `$PORT` (8080) via `main.py` |
| Service account | `persona-voice-run@eseller-ai.iam.gserviceaccount.com` | runtime identity (ADC for Gemini + Maps) |
| Roles | `roles/aiplatform.user`, `roles/serviceusage.serviceUsageConsumer` (project); `storage.objectAdmin` (bucket); `secretmanager.secretAccessor` (secret) | least privilege; serviceUsageConsumer is needed for the `X-Goog-User-Project` header on Maps calls |
| Bucket | `gs://eseller-ai-persona-voice-data` (private, public access prevention) | mounted at `/data` = `DATA_DIR` (personas, places.json, voices.json) via Cloud Storage FUSE, `uid=1000;gid=1000` (container runs as `appuser` 1000) |
| Secret | `fish-audio-api-key` | → env `FISH_AUDIO_API_KEY` |
| Artifact Registry | `cloud-run-source-deploy` | images from `--source` builds |

## Runtime settings and why

- `--max-instances 1`: the file-based store (JSON/npy on GCS FUSE) isn't safe across concurrent instances;
  also caps spend while the URL is public.
- `--no-cpu-throttling`: persona builds run as FastAPI BackgroundTasks *after* the response; with
  request-based CPU they'd stall. Min instances 0 → scales to zero when idle (cold start ~ a few s).
- `--execution-environment gen2`: required for volume mounts. `--timeout 600` for long streams/builds.
- `ENVIRONMENT=prod` → no `/docs`, `/redoc`, `/openapi.json`; no reload.

## Access — PUBLIC (user's choice, 2026-10-24)

`--allow-unauthenticated`: anyone with the URL can chat, read personas/saved places and spend Gemini,
Fish and Maps credits. There is no app login yet — **adding one is the top follow-up** (or switch to
private: `gcloud run services remove-iam-policy-binding persona-voice --region asia-south1
--member=allUsers --role=roles/run.invoker`, then `gcloud run services proxy persona-voice --region asia-south1`).

## Verified after deploy

Health, SPA, Gemini chat + streamed Fish audio (first event 1.2 s), location draft via Maps with the
service account (CP → Sector 15 Noida), bucket writes (`personas/builtin_overrides.json`), no ERROR logs.
