SHELL := /bin/bash
.DEFAULT_GOAL := help

BACKEND_DIR := backend
FRONTEND_DIR := frontend
PYTHON ?= python3.12
VENV := $(BACKEND_DIR)/.venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: help install install-backend install-frontend dev test test-backend test-frontend \
	lint lint-backend lint-frontend typecheck typecheck-backend typecheck-frontend \
	format migrate seed docker-up docker-down docker-logs

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "%-18s %s\n", $$1, $$2}'

install: install-backend install-frontend ## Install backend and frontend dependencies

$(PY):
	$(PYTHON) -m venv $(VENV)

install-backend: $(PY) ## Create the venv and install backend dependencies
	$(PIP) install --upgrade pip
	$(PIP) install -r $(BACKEND_DIR)/requirements-dev.txt

install-frontend: ## Install frontend dependencies from the lockfile
	cd $(FRONTEND_DIR) && npm ci

dev: ## Run the API and the web app together
	@trap 'kill $$(jobs -p) 2>/dev/null' EXIT INT TERM; \
	(cd $(BACKEND_DIR) && .venv/bin/uvicorn app.main:app --reload --port 8000) & \
	(cd $(FRONTEND_DIR) && npm run dev) & \
	wait

test: test-backend test-frontend ## Run all backend and frontend tests

test-backend: ## Run backend tests
	cd $(BACKEND_DIR) && .venv/bin/python -m pytest

test-frontend: ## Run frontend unit tests
	cd $(FRONTEND_DIR) && npm test --silent

lint: lint-backend lint-frontend ## Lint backend and frontend

lint-backend: ## Run ruff and mypy on the backend
	cd $(BACKEND_DIR) && .venv/bin/ruff check . && .venv/bin/ruff format --check .
	cd $(BACKEND_DIR) && .venv/bin/mypy app tests

lint-frontend: ## Run ESLint on the frontend
	cd $(FRONTEND_DIR) && npm run lint --silent

typecheck: typecheck-backend typecheck-frontend ## Type-check both projects

typecheck-backend: ## Run mypy
	cd $(BACKEND_DIR) && .venv/bin/mypy app tests

typecheck-frontend: ## Run tsc --noEmit
	cd $(FRONTEND_DIR) && npm run typecheck --silent

format: ## Auto-format the backend
	cd $(BACKEND_DIR) && .venv/bin/ruff check --fix . && .venv/bin/ruff format .

migrate: ## Apply database migrations
	cd $(BACKEND_DIR) && .venv/bin/alembic upgrade head

seed: ## Load seed data
	cd $(BACKEND_DIR) && .venv/bin/python -m app.seed

docker-up: ## Build and start the full local stack
	docker compose up --build -d

docker-down: ## Stop the local stack and remove volumes
	docker compose down -v

docker-logs: ## Follow logs from all services
	docker compose logs -f
