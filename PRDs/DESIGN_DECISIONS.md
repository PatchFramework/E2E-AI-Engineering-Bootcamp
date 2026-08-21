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

## Data Pipelines & Ingestion Decisions

- **Decision**: Automatic metadata extraction on PDF uploads.
  - **Details**: The upload API dynamically extracts the company, fiscal year (YYYY format), fiscal period (e.g., Q1, FY26), and document type (e.g., 10-K, 10-Q) using a lightweight LLM call (`gpt-4o-mini`) on the first 3 pages of the PDF.
  - **Rationale**: Removes manual work and ensures naming/metadata consistency.

- **Decision**: MinIO Path & PDF Naming Standard.
  - **Details**: Store original files at:
    `filings/{company_id}/{fiscal_year}_{fiscal_period}/{document_type}_{content_hash}.pdf`
  - **Rationale**: Clear organization that prevents conflicts and identifies documents at a glance.

- **Decision**: Prioritized Deterministic Parsing with OpenAI Vision OCR Fallback.
  - **Details**:
    - We use PyMuPDF to extract text, bounding boxes, and tables.
    - If a page has < 100 characters of selectable text or is detected as a scanned page, we trigger **OpenAI Vision OCR** fallback using `gpt-4o-mini` on the rendered page image.
  - **Rationale**: Bypasses heavy system dependencies (like Tesseract binaries) in the Airflow container while handling horizontal, double-column, or scanned formats robustly.

- **Decision**: In-depth Accounting Validations & Reconciliation Issues.
  - **Details**: Perform deep accounting validation without simplifications. Mismatches and prior-year comparison reconciliations are stored in a new `data_quality_issues` table in PostgreSQL.
  - **Rationale**: Provides the core data required for the analyst reconciliation dashboard.

- **Decision**: Vector Chunk Metadata Enrichment & Strict Company Isolation.
  - **Details**:
    - Chunks are stored in `document_chunks` partitioned strictly by `company_id` (cross-company search is out-of-scope).
    - Chunks are annotated with concepts they contain (e.g., `ebitda`) and the derived metrics they affect (e.g., `net_debt_to_ebitda`).
  - **Rationale**: Restricts access context and enhances citation mapping.

- **Decision**: Dual Page Numbering (Physical Index vs. Displayed Page Number).
  - **Details**:
    - Both `SourceLocation` and `DocumentChunk` store `page_number` (the 1-based index of the PDF file) and `displayed_page_number` (the page label printed on the page, like Roman numerals or offset digits).
  - **Rationale**: Keeps full compatibility with UI PDF renders (which require physical indexes) and citations (which require printed labels).

- **Decision**: Navigation & Irrelevant Page Filtering.
  - **Details**:
    - Table of Contents, cover pages, and empty navigational spacer pages are detected during layout analysis and excluded from vector chunking/indexing.
  - **Rationale**: Eliminates useless search hits and improves token usage.

## Credit Underwriting Copilot & Agent Architecture

- **Decision**: Omnipresent Resizable Copilot Panel.
  - **Details**: The Copilot is elevated to the global application layout (`App.tsx`), accessible on all screens with a horizontal drag-to-resize handle (dynamic width between 360px and 800px) and a toggle-to-collapse trigger.
  - **Rationale**: Analysts need side-by-side access to the Copilot during filing uploads, KPI inspection, and fact corrections. Resizing allows expanding the panel when viewing complex dynamic data visualizations.

- **Decision**: Eager Minimal Context Ingestion + On-Demand Retrieval.
  - **Details**: The UI automatically injects active navigation state, active company, open KPI/facts, and open document/page pointers in the chat request. Detailed data is NOT dumped into the prompt; instead, the agent is equipped with deterministic tools to query relevant facts, chunks, and history dynamically.
  - **Rationale**: Keeps prompt token usage lean and eliminates hallucinated or stale context while empowering the agent to fetch precise records.

- **Decision**: LangGraph Multi-Skill Architecture with LangSmith Tracing.
  - **Details**: Copilot backend is organized as a LangGraph state graph with a supervisor node and specialized skills (Document/RAG, Financial Analysis, Data Quality/Audit, Dynamic Dashboard Builder). All runs are traced in LangSmith with metadata tags (`company_id`, `session_id`).
  - **Rationale**: Modular, inspectable tool routing prevents tool-selection confusion and ensures complete auditability of reasoning steps.

- **Decision**: Deterministic Financial Tools over LLM Arithmetic.
  - **Details**: All numerical evaluations, metric histories, single-metric checks, formula resolutions, and accounting aggregations are executed via deterministic Python services (`MetricCalculationService`) and database queries.
  - **Rationale**: LLMs are unreliable at arithmetic. Strict separation guarantees 100% mathematical accuracy.

- **Decision**: Generative UI Native Widgets with Pydantic Validation & Image Export.
  - **Details**: For visual answers, the agent produces structured JSON widget specifications (Line charts, Bar charts, Pie charts, Word Clouds / Concept Frequency). Specs are validated against strict Pydantic schemas with automatic LLM self-correction retries if malformed. The frontend renders them with Recharts and provides one-click PNG/SVG download.
  - **Rationale**: Delivers interactive, responsive native visualizations without arbitrary code execution risks, with guaranteed schema safety and exportability.

- **Decision**: Grounded PDF Citations & Bounding-Box Navigation.
  - **Details**: Every factual claim and financial fact used by the agent includes structured citation metadata (`document_id`, `page_number`, `bounding_box`). Clicking any citation in the chat navigates the UI document preview directly to the target page and highlights the bounding box.
  - **Rationale**: Maintains the core product pillar of complete evidence provenance and zero ungrounded assertions.

- **Decision**: SSE Streaming, Human-Friendly Reasoning States & PostgreSQL Session Persistence.
  - **Details**: The agent communicates over Server-Sent Events (SSE), streaming tokens and human-friendly reasoning step updates (`"Searching filing debt schedule..."`, `"Calculating 5-year leverage history..."`). Analysts can abort active generations, start fresh chat sessions, and switch between past conversations persisted in PostgreSQL (`chat_sessions`, `chat_messages`).
  - **Rationale**: Delivers high responsiveness, clear visibility into backend tool executions, and audit-compliant conversation tracking.



