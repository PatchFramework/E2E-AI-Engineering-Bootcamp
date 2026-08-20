.PHONY: help setup run-docker-compose run-api run-ui test test-api test-pipelines

help:
	@echo "========================================================================"
	@echo "🏦 AI-Assisted Credit Underwriting Platform - Makefile Reference"
	@echo "========================================================================"
	@echo "Setup Commands:"
	@echo "  setup                  - Initialize project: copy .env and sync dependencies"
	@echo ""
	@echo "Docker Commands:"
	@echo "  run-docker-compose     - Build and start all services via Docker Compose"
	@echo ""
	@echo "Local Execution Commands:"
	@echo "  run-api                - Start the FastAPI backend server locally"
	@echo "  run-ui                 - Start the React Analyst UI locally"
	@echo ""
	@echo "Testing Commands:"
	@echo "  test                   - Run all backend and pipeline test suites"
	@echo "  test-api               - Run API test suite"
	@echo "  test-pipelines         - Run Airflow pipeline task test suite"
	@echo "========================================================================"

setup:
	@if [ ! -f .env ]; then \
		cp env.example .env; \
		echo "✅ Created .env from env.example. Please populate your API keys!"; \
	else \
		echo "ℹ️ .env already exists."; \
	fi
	@if [ ! -d .venv ]; then \
		echo "📦 Creating virtual environment (.venv) using Python 3.12..."; \
		uv venv .venv --python 3.12; \
	else \
		echo "ℹ️ Virtual environment (.venv) already exists."; \
	fi
	@echo "🔄 Synchronizing workspace dependencies..."
	uv sync

run-docker-compose:
	docker compose up --build

run-api:
	PYTHONPATH=apps/api/src uv run --env-file .env uvicorn api.app:app --host 0.0.0.0 --port 8000 --reload

run-ui:
	cd apps/analyst_ui && npm run dev

test: test-api test-pipelines

test-api:
	uv run pytest apps/api/tests/ -v

test-pipelines:
	uv run pytest apps/pipelines/tests/ -v