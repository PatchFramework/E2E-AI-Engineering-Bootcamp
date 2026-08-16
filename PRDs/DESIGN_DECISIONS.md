# Key Design Decisions

This document summarizes the core architectural and implementation decisions
agreed upon during the early setup phase. These decisions override or clarify
any conflicting notes in the original drafts.

## Database Versioning & Migrations

- **Decision**: We will use **Alembic** inside `apps/api` immediately to manage
  PostgreSQL database migrations.
- **Rationale**: The database schema (such as `financial_facts` versioning and
  audit trails) is highly relational and complex. Tracking changes through
  code-controlled migrations ensures reliability across environment changes.

## Metric Recalculations

- **Decision**: All derived metric recalculations will happen **synchronously**
  in the backend API (e.g. within `MetricCalculationService`) reactively upon
  every analyst correction.
- **Rationale**: This guarantees immediate consistency on the dashboard without
  introducing the overhead of background workers or message queues (like
  Celery/RabbitMQ) for the MVP.

## PDF Ingestion, Hashing & Processing Bypass

- **Decision**:
  - Raw PDFs are stored in MinIO, with metadata and SHA-256 hashes recorded in
    PostgreSQL.
  - If a document is uploaded with a SHA-256 hash **identical** to an existing
    record, the ingestion and extraction pipeline **will be bypassed entirely**
    (the document will not be reprocessed).
  - Reprocessing will only trigger if the file hash changes (implying a new file
    or version), assuming the core preprocessing/extraction code remains
    unchanged.
- **Rationale**: Avoids unnecessary LLM extraction costs and redundant API
  processing.

## Frontend Technology Stack

- **Decision**: Completely deprecate and replace the Streamlit frontend
  (`apps/chatbot_ui`) with a React + TypeScript + Tailwind CSS application
  (`apps/analyst_ui`).
- **Rationale**: Aligns the codebase with the `UI_PRD.md` and allows a rich
  analyst dashboard experience.

## Storage Consolidation

- **Decision**: Consolidate database storage into a single PostgreSQL engine
  using the **`pgvector`** extension (`pgvector/pgvector:16-pgvector` official
  image). Qdrant will be deprecated and removed from the docker-compose
  services.
- **Rationale**: Simplifies local orchestration and satisfies the PRD
  requirement of avoiding an independent vector DB for the MVP.
