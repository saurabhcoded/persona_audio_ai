COMPOSE_DEV = docker compose -f docker-compose.yml -f docker-compose.dev.yml

.PHONY: env install run web web-build test lint format dev up down logs build shell

env:            ## Create .env from template if missing
	@test -f .env || cp .env.example .env

install:        ## Install backend + frontend deps
	pip install -r requirements-dev.txt
	cd frontend && npm install

run: env        ## Run locally with reload
	uvicorn app.main:app --reload

web:            ## Run Vite dev server (proxies /api to :8000)
	cd frontend && npm run dev

web-build:      ## Build frontend into frontend/dist (served by FastAPI)
	cd frontend && npm run build

test:           ## Run tests
	pytest -q

lint:
	ruff check .

format:
	ruff format . && ruff check --fix .

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
