# 🚀 E2E AI Engineering Bootcamp - Student Submission

> **Cohort Coursework & Project Submission**: This repository will contain my submissions for the **E2E AI Engineering Bootcamp**. It currently is a modified version of the **Product Support Chatbot** use-case discussed in the first week of the bootcamp and will be modified along the way of the cohort, probably shifting the use-case.

---

## 📋 Table of Contents

- [📁 Project Structure](#-project-structure)
- [⚙️ Prerequisites](#️-prerequisites)
- [⚠️ Critical Startup Dependency & Data Pipeline](#️-critical-startup-dependency--data-pipeline)
- [🛠️ Getting Started](#️-getting-started)
  - [Option A: Automated Setup (via Makefile)](#option-a-automated-setup-via-makefile)
  - [Option B: Manual Setup](#option-b-manual-setup)
- [📓 Jupyter Notebooks](#-jupyter-notebooks)
- [🧹 Cleaning up Notebooks](#-cleaning-up-notebooks)
- [📊 Evaluation Scripts](#-evaluation-scripts)
- [📝 Makefile Command Reference](#-makefile-command-reference)
- [📚 Citation & Datasets](#-citation--datasets)

---

## 📁 Project Structure

```text
├── apps/
│   ├── api/                   # FastAPI backend service
│   │   ├── src/api/app.py     # API entrypoint
│   │   └── evals/             # Evaluation scripts (e.g. retriever evals)
│   └── chatbot_ui/            # Streamlit Chatbot UI service
│       └── src/...            # Frontend chatbot interface
├── notebooks/                 # Weekly cohort Jupyter Notebooks
│   ├── prerequisites/         # Environment setup and LLM API tests
│   └── week_1/                # Week 1 notebook exercises (Data explore, RAG, Observability)
├── documentation/             # Markdown guides and resources
│   └── development-environment/ # Python and Docker environmental setup guide
├── docker-compose.yml         # Local orchestration for all services
├── env.example                # Example configuration template
└── Makefile                   # Task runner for environment setup and service startup
```

For a detailed walkthrough on setting up your local OS and environment, please refer to the [Development Environment Setup Guide](documentation/development-environment/README.md).

---

## ⚙️ Prerequisites

Before running the project, make sure you have the following installed locally:

1. **Python 3.12+**
2. **[uv](https://github.com/astral-sh/uv)**: A fast Rust-based Python package and project manager. We use `uv` to handle local virtual environments (`uv venv`) and lock/sync dependencies (`uv sync`) at the workspace level.
3. **Docker & Docker Desktop**: Required for containerized service execution (Qdrant, API, Streamlit).

### How Virtual Environments and Dependency Synchronization Work with `uv`

Instead of utilizing standard `venv` and `pip`, this repository utilizes **`uv`** for managing dependencies and environments:
* **Virtual Environment Creation**: Running `uv venv .venv --python 3.12` creates a local, isolated virtual environment named `.venv` in your project root using Python 3.12.
* **Dependency Synchronization**: Running `uv sync` parses your workspace’s `pyproject.toml` and locks it, installing exactly the resolved packages into your active `.venv`. It automatically removes any packages that are no longer declared, keeping your environment perfectly in sync with the project definition.

---

## 🔑 Environment Setup

Configure API keys and environmental variables by setting up your `.env` file:

1. Duplicate [env.example](env.example) and name it `.env`:
   ```bash
   cp env.example .env
   ```
2. Open the newly created `.env` file and populate it with your keys:
   ```env
   OPENAI_API_KEY=your_openai_api_key
   LANGSMITH_API_KEY=your_langsmith_api_key
   LANGSMITH_TRACING=true
   LANGSMITH_ENDPOINT=https://api.smith.langchain.com
   LANGSMITH_PROJECT="e2e-ai-eng"
   ```

---

## ⚠️ Critical Startup Dependency & Data Pipeline

> The Docker Compose stack and local services have a direct startup dependency on the data preprocessing pipeline. You **cannot** run the complete chatbot or API stack successfully until the Qdrant database has been populated with embeddings.
>
> Follow this specific sequence to bootstrap the environment:
>
> 1. **Spin up Qdrant first**: You must start the Qdrant container before anything else.
> 2. **Run the preprocessing notebook**: Open and execute the Jupyter notebook [02-RAG-preprocessing-items.ipynb](notebooks/week_1/02-RAG-preprocessing-items.ipynb). This notebook downloads the raw Amazon dataset, cleans it, extracts the product subset, computes embeddings, and uploads them to your running Qdrant instance.
> 3. **Run the backend/UI stack**: Once Qdrant has been populated by the notebook, you can start the FastAPI backend and Streamlit UI (via Docker Compose or local commands as shown below).

---

## 🛠️ Getting Started

To support different development workflows, there is a clear separation between an **automated setup using the Makefile** and a **manual setup using step-by-step commands**. Choose one of the options below.

---

### Option A: Automated Setup (via Makefile)

This path utilizes our `Makefile` to automate the setup process in an idempotent manner. 

When you run `make setup`, the script performs the following actions automatically under the hood:
1. **Creates the `.env` file**: Copies `env.example` to `.env` (it will not overwrite your existing `.env` file if it is already present).
2. **Creates a local virtual environment**: Runs `uv venv .venv --python 3.12` to create a clean virtual environment in the project root folder if it is missing.
3. **Installs and synchronizes all dependencies**: Runs `uv sync` to install all workspace and package requirements listed in the lockfile into the active `.venv`.

#### Execution Steps:
1. **Initialize the workspace**:
   ```bash
   make setup
   ```
2. **Configure API Keys**: Open the newly created `.env` file and set your `OPENAI_API_KEY` and `LANGSMITH_API_KEY`.
3. **Boot the Vector Database**:
   ```bash
   make run-qdrant
   ```
4. **Index the Database**: Start Jupyter Lab:
   ```bash
   uv run --with jupyter jupyter lab
   ```
   Open and execute all cells in [02-RAG-preprocessing-items.ipynb](notebooks/week_1/02-RAG-preprocessing-items.ipynb) to seed the database with product embeddings.
5. **Run the complete service stack**:
   ```bash
   make run-docker-compose
   ```
   _Alternatively, run services individually outside of Compose_:
   - Backend API: `make run-api`
   - Frontend Streamlit UI: `make run-ui`

---

### Option B: Manual Setup

If you prefer to configure the environment manually without using the Makefile, run the following commands:

1. **Configure Environment File**:
   Create your local `.env` configuration:
   ```bash
   cp env.example .env
   ```
   *Open `.env` and fill in your `OPENAI_API_KEY` and `LANGSMITH_API_KEY`.*

2. **Initialize Local Virtual Environment**:
   Create a local virtual environment (`.venv`) explicitly pinned to Python 3.12 using `uv`:
   ```bash
   uv venv .venv --python 3.12
   ```

3. **Install Workspace Dependencies**:
   Install and sync all required Python packages into your newly created `.venv`:
   ```bash
   uv sync
   ```

4. **Spin up Qdrant Vector DB**:
   Start Qdrant locally in a detached Docker container:
   ```bash
   docker run -d --name qdrant-local -p 6333:6333 -p 6334:6334 -v $(pwd)/qdrant_data:/qdrant/storage qdrant/qdrant
   ```

5. **Run the Preprocessing & Seeding Pipeline**:
   Start Jupyter Lab:
   ```bash
   uv run --with jupyter jupyter lab
   ```
   Navigate to [02-RAG-preprocessing-items.ipynb](notebooks/week_1/02-RAG-preprocessing-items.ipynb) and run all cells to generate and store product embeddings.

6. **Run backend and Streamlit UI services locally**:
   - **Start the FastAPI Backend**:
     ```bash
     PYTHONPATH=apps/api/src uv run --env-file .env uvicorn api.app:app --host 0.0.0.0 --port 8000 --reload
     ```
     _The API will be available at [http://localhost:8000](http://localhost:8000)_
   - **Start the Streamlit Chatbot UI**:
     ```bash
     PYTHONPATH=apps/chatbot_ui/src uv run --env-file .env streamlit run apps/chatbot_ui/src/chatbot_ui/app.py --server.port 8501
     ```
     _The chatbot interface will open at [http://localhost:8501](http://localhost:8501)_

---

## 📓 Jupyter Notebooks

This project contains several notebooks for week 1 of the E2E Bootcamp under the [notebooks/](notebooks/) directory. To run notebooks locally with `uv` dependencies, run:

```bash
uv run --with jupyter jupyter lab
```

You can also use **Cursor** or **VSCode** directly by selecting the `.venv` virtual environment as your Jupyter kernel.

---

## 🧹 Cleaning up Notebooks

Before making git commits, it is best practice to clear notebook outputs to keep the repository clean and small.

Use the Makefile helper to clear outputs in all notebooks:
```bash
make clean-notebook-outputs
```

Or run manually:
```bash
jupyter nbconvert --clear-output --inplace notebooks/*/*.ipynb
```

---

## 📊 Evaluation Scripts

This repository contains evaluation scripts to score and benchmark retriever pipelines.

To run the evaluations:
```bash
make run-evals-retriever
```

Or run manually:
```bash
PYTHONPATH=${PWD}/apps/api:${PWD}/apps/api/src:$PYTHONPATH:${PWD} uv run --env-file .env python -m evals.eval_retriever
```

---

## 📝 Makefile Command Reference

Below is a summary of all commands configured in the [Makefile](Makefile):

| Command                       | Action                                                                       |
| :---------------------------- | :--------------------------------------------------------------------------- |
| `make help`                   | Prints the interactive Makefile help reference.                              |
| `make setup`                  | Installs dependencies with `uv` and copies environment variables if missing. |
| `make run-docker-compose`     | Builds and runs API, Streamlit, and Qdrant via Docker Compose.               |
| `make run-qdrant`             | Starts a standalone local Qdrant container.                                  |
| `make run-api`                | Runs the FastAPI backend server locally with hot-reloading.                  |
| `make run-ui`                 | Runs the Streamlit chatbot UI locally.                                       |
| `make run-evals-retriever`    | Runs retrieval evaluation scripts locally.                                   |
| `make clean-notebook-outputs` | Removes output data from all notebook files before commit.                   |

---

## 📚 Citation & Datasets

This repository uses datasets provided by the authors of the paper: _"Bridging Language and Items for Retrieval and Recommendation"_.

If you use this work or dataset in your studies, please cite:

```bibtex
@article{hou2024bridging,
  title={Bridging Language and Items for Retrieval and Recommendation},
  author={Hou, Yupeng and Li, Jiacheng and He, Zhankui and Yan, An and Chen, Xiusi and McAuley, Julian},
  journal={arXiv preprint arXiv:2403.03952},
  year={2024}
}
```
