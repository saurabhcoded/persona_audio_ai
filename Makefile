COMPOSE_DEV = docker compose -f docker-compose.yml -f docker-compose.dev.yml

.PHONY: env install run web web-build test lint format dev up down logs build shell deploy deploy-logs

env:            ## Create .env from template if missing
	@test -f .env || cp .env.example .env

install:        ## Install backend (uv) + frontend deps
	uv sync
	cd frontend && npm install

run: env        ## Run locally (reloads when ENVIRONMENT=local)
	uv run main.py

web:            ## Run Vite dev server (proxies /api to :8000)
	cd frontend && npm run dev

web-build:      ## Build frontend into frontend/dist (served by FastAPI)
	cd frontend && npm run build

test:           ## Run tests
	uv run pytest -q

lint:
	uv run ruff check .

format:
	uv run ruff format . && uv run ruff check --fix .

dev: env        ## Docker: api + vite dev server with hot reload
	$(COMPOSE_DEV) up --build

up: env         ## Docker: prod-like stack (detached)
	docker compose up --build -d

down:
	$(COMPOSE_DEV) down

logs:
	docker compose logs -f api

build:
	docker compose build

shell:
	docker compose exec api sh

# ---------- Google Cloud Run (see agents/knowledge/deployment.md) ----------
GCP_PROJECT ?= eseller-ai
GCP_REGION ?= asia-south1
SERVICE ?= persona-voice

deploy:         ## Build with Cloud Build and deploy to Cloud Run
	gcloud run deploy $(SERVICE) --source . --project $(GCP_PROJECT) --region $(GCP_REGION) --quiet \
	  --service-account persona-voice-run@$(GCP_PROJECT).iam.gserviceaccount.com --allow-unauthenticated \
	  --execution-environment gen2 --no-cpu-throttling --min-instances 0 --max-instances 1 \
	  --memory 1Gi --cpu 1 --timeout 600 --concurrency 40 \
	  --set-env-vars ENVIRONMENT=prod,DEBUG=false,LOG_LEVEL=INFO,DATA_DIR=/data,GCP_PROJECT=$(GCP_PROJECT) \
	  --set-secrets FISH_AUDIO_API_KEY=fish-audio-api-key:latest \
	  --add-volume "name=data,type=cloud-storage,bucket=$(GCP_PROJECT)-persona-voice-data,mount-options=uid=1000;gid=1000" \
	  --add-volume-mount volume=data,mount-path=/data

deploy-logs:    ## Recent Cloud Run logs
	gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="$(SERVICE)"' \
	  --project $(GCP_PROJECT) --freshness=1h --limit 50 --format="value(timestamp,severity,textPayload)"
