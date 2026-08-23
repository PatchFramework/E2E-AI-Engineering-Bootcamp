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

- **Decision**: Centralized Hub-and-Spoke Topology with Dynamic Plan Re-evaluation.
  - **Details**: 
    - The Copilot is built as a LangGraph Hub-and-Spoke state graph where the **Orchestrator Hub** generates structured execution plans (`OrchestrationPlan`), delegates targeted subtasks to specialized subagents (`FinancialMetricAgent`, `AgenticRAGAgent`, `DataQualityAgent`, `GenUIWidgetAgent`), and inspects subagent outputs upon completion.
    - Subagents always report back to the Orchestrator Hub rather than daisy-chaining directly between themselves. This enables the Orchestrator to assess if output goals were met, dynamically refine the plan if information is missing or unexpected, and assign subsequent steps with full awareness.
  - **Rationale**: Keeps graph topology manageable, prevents uncontrolled inter-subagent cascades, and enables dynamic replanning based on intermediate evidence.

- **Decision**: Forced Tool Calling (`tool_choice="required"`) Across Subagents.
  - **Details**: Every domain subagent binds its compartmentalized tool suite using `ChatOpenAI.bind_tools(tools, tool_choice="required")`.
  - **Rationale**: Prevents LLMs from attempting internal unverified mental arithmetic or hallucinated facts. Forces deterministic computation and verifiable SQL/vector retrieval.

- **Decision**: Subagent Substate Isolation & Tool Call Error Tracking.
  - **Details**: Each subagent operates on its own dedicated substate (`SubagentSubstate`) with fields for `task_description`, `iteration_count`, `tool_call_history` (`ToolCallRecord`), `internal_messages`, and `final_summary`. If a tool execution fails, the error status and message are stored in history, allowing the subagent to iterate and correct arguments rather than crashing.
  - **Rationale**: Isolates scratchpad context to avoid cross-agent context contamination, and allows self-healing retry loops within subagent execution cycles.

- **Decision**: Clean Chronological Event Timeline (`clean_event_history`) for Synthesis.
  - **Details**: Instead of passing raw SQL dumps, unformatted JSON arrays, or verbose tool messages to the Synthesizer, an append-only timeline reducer (`append_clean_events`) records structured `CleanEvent` items (`USER_QUERY`, `ORCHESTRATOR_PLAN`, `DELEGATED_TASK`, `SUBAGENT_ANSWER`, `GEN_UI_SPEC`, `PLAN_REFINED`). The Synthesizer consumes this clean narrative to produce final markdown credit memos.
  - **Rationale**: Prevents prompt token bloat in the synthesis step, eliminates hallucinations from noisy raw data, and aligns the synthesizer's mental model directly with the orchestrator's decision trail.

- **Decision**: Comprehensive Token & Cost Accounting across LangGraph Nodes.
  - **Details**: All nodes record token consumption into an accumulated token usage dictionary (`accumulate_tokens` reducer). Token counts (`prompt_tokens`, `completion_tokens`, `cached_tokens`, `reasoning_tokens`, `total_tokens`) are recorded in LangSmith trace runs, persisted in PostgreSQL `chat_messages.tool_calls`, and emitted in the SSE `done` event.
  - **Rationale**: Provides granular visibility into LLM operating costs, token distribution per subagent, and cache efficiency.

- **Decision**: Generative UI Tool Binding with 3-Retry Self-Correction Loop.
  - **Details**: For visual answers, the GenUI agent binds typed chart constructor tools (`build_line_chart_spec`, `build_bar_chart_spec`, `build_pie_chart_spec`, `build_word_cloud_spec`) with `tool_choice="required"`. Specs are validated against strict Pydantic schemas in a dedicated validator node with up to 3 automatic correction retries before gracefully degrading to `TableWidgetSpec`. The frontend renders them with Recharts and provides one-click PNG/SVG download.
  - **Rationale**: Delivers interactive, responsive native visualizations without arbitrary code execution risks, with guaranteed schema safety and exportability.

- **Decision**: Agentic Hybrid RAG with Keyword/Dense Weighting & Tunable Scope.
  - **Details**: Vector search in `pgvector` is upgraded to Agentic Hybrid RAG where the agent can dynamically tune semantic vs. exact keyword matching (BM25/PostgreSQL full-text) and set retrieval bounds (`limit`, `section_filter`). Exact keyword search is used for term frequency and word cloud generation.
  - **Rationale**: Certain underwriting questions require exact debt covenant keyword matches, while others require high-level conceptual thematic similarity.

- **Decision**: LangSmith Prompt Hub Integration, Versioning & Feedback Propagation.
  - **Details**: All system and agent prompts are pulled dynamically from the LangSmith Prompt Hub (with version pinning and in-memory caching) with an embedded local fallback prompt for offline resilience. Tracing captures `company_id`, `session_id`, `user_id`, and `active_metric`. User thumbs up/down and fact corrections propagate directly to LangSmith trace runs.
  - **Rationale**: Enables prompt experimentation, prompt evaluation datasets, and end-to-end trace auditing.

- **Decision**: Grounded Citations & Pydantic Source Schema.
  - **Details**: All retrieved context, SQL facts, and filing chunks are structured via a Pydantic `CitationSource` schema with exact page numbers, displayed page numbers, and bounding-box coordinates. Citations are emitted both inline and as a complete structured appendix in the SSE event payload for analyst verification.
  - **Rationale**: Ensures complete, verifiable evidence provenance and zero hallucinated sources.

- **Decision**: Conversation Token Budgeting, State Pruning & Graph Cancellation.
  - **Details**:
    - LangGraph state pruning cleans out intermediate tool execution payloads older than 3 turns.
    - Active conversation context is capped at 10 turns per session.
    - Strict `company_id` parameter injection is enforced across all graph subagents and database queries.
    - Client UI disconnects / stop actions propagate directly to graph task cancellation.
  - **Rationale**: Prevents token limit exhaustion, guarantees multi-tenant isolation, and prevents runaway cloud LLM costs.

- **Decision**: SSE Streaming, Human-Friendly Reasoning States & PostgreSQL Session Persistence.
  - **Details**: The agent communicates over Server-Sent Events (SSE), streaming tokens and human-friendly reasoning step updates (`"Searching filing debt schedule..."`, `"Calculating 5-year leverage history..."`). Analysts can abort active generations, start fresh chat sessions, and switch between past conversations persisted in PostgreSQL (`chat_sessions`, `chat_messages`).
  - **Rationale**: Delivers high responsiveness, clear visibility into backend tool executions, and audit-compliant conversation tracking.





