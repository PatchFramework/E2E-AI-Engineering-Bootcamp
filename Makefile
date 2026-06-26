.PHONY: help setup run-docker-compose run-qdrant run-api run-ui run-evals-retriever clean-notebook-outputs

help:
	@echo "========================================================================"
	@echo "🚀 E2E AI Engineering Bootcamp Makefile Command Reference"
	@echo "========================================================================"
	@echo "Setup Commands:"
	@echo "  setup                  - Initialize project: copy .env and sync dependencies"
	@echo ""
	@echo "Docker Commands:"
	@echo "  run-docker-compose     - Build and start all services (API, UI, Qdrant) via Docker Compose"
	@echo "  run-qdrant             - Start Qdrant database in a standalone Docker container"
	@echo ""
	@echo "Local Execution Commands (requires local Qdrant running):"
	@echo "  run-api                - Start the FastAPI backend server locally"
	@echo "  run-ui                 - Start the Streamlit chatbot UI locally"
	@echo ""
	@echo "Evaluation & Utility Commands:"
	@echo "  run-evals-retriever    - Run the retriever evaluation script"
	@echo "  clean-notebook-outputs - Clear output cells in all Jupyter Notebooks"
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
	uv sync
	docker compose up --build

run-qdrant:
	docker run -d --name qdrant-local -p 6333:6333 -p 6334:6334 -v $$(pwd)/qdrant_data:/qdrant/storage qdrant/qdrant || docker start qdrant-local

run-api:
	PYTHONPATH=apps/api/src uv run --env-file .env uvicorn api.app:app --host 0.0.0.0 --port 8000 --reload

run-ui:
	PYTHONPATH=apps/chatbot_ui/src uv run --env-file .env streamlit run apps/chatbot_ui/src/chatbot_ui/app.py --server.port 8501

run-evals-retriever:
	uv sync
	PYTHONPATH=${PWD}/apps/api:${PWD}/apps/api/src:$$PYTHONPATH:${PWD} uv run --env-file .env python -m evals.eval_retriever

clean-notebook-outputs:
	jupyter nbconvert --clear-output --inplace notebooks/*/*.ipynb