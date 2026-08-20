# Financial Ingestion Pipeline (`financial_ingestion_dag`)

This directory houses the Apache Airflow data ingestion and processing pipelines
for the AI-Assisted Credit Underwriting platform. The primary workflow is
defined in
[`dags/financial_ingestion_dag.py`](./dags/financial_ingestion_dag.py),
orchestrating the end-to-end ingestion of corporate financial filings (PDFs),
structured fact extraction, accounting validation, semantic vector chunking, and
derived KPI metric calculation.

---

## 1. High-Level System Architecture & DAG Mapping

The diagram below illustrates how each task in `financial_ingestion_dag`
interacts with external components (MinIO, OpenAI API, PostgreSQL / pgvector)
and executes core business logic.

```mermaid
flowchart TD
    subgraph Trigger["1. Trigger & Orchestration"]
        API["FastAPI Backend\n(/documents/upload)"] -->|"Trigger DAG Run\n(REST API)"| AF["Airflow Scheduler / DAG\n(financial_ingestion_dag)"]
    end

    subgraph DAG["Airflow DAG Execution Flow"]
        T1["Task 1: parse_pdf\n(PyMuPDF + Vision OCR)"]
        T2["Task 2: extract_facts\n(Instructor + LLM)"]
        T3["Task 3: validate_facts\n(Accounting Engine)"]
        T4["Task 4: calculate_kpis\n(MetricCalculationService)"]
        T5["Task 5: index_chunks\n(pgvector RAG Indexing)"]

        T1 -->|"XCom: parsed_data"| T2
        T2 -->|"XCom: extraction_result"| T3
        T3 -->|"Sequential dependency"| T4
        T1 -->|"XCom: parsed_data\n(Parallel branch)"| T5
    end

    subgraph External["External Systems & Storage"]
        S3[("MinIO Object Storage\n(S3-compatible)")]
        OAI["OpenAI API\n(gpt-4o-mini & embeddings)"]
        DB[("PostgreSQL Database\n(+ pgvector extension)")]
    end

    %% External Connections
    AF -->|"Dispatches Task"| T1
    T1 <-->|"1. Download PDF\n2. Upload page PNGs"| S3
    T1 -.->|"OCR fallback (scanned pages)"| OAI

    T2 <-->|"Fetch doc metadata\n& Write Facts + SourceLocations"| DB
    T2 <-->|"Structured extraction (JSON schema)"| OAI

    T3 <-->|"Read active facts & Write DataQualityIssues"| DB

    T4 <-->|"Read facts & Upsert DerivedMetricValues + Lineage"| DB

    T5 <-->|"Generate embeddings (text-embedding-3-small)"| OAI
    T5 <-->|"Save DocumentChunks with 1536-dim vectors"| DB

    classDef trigger fill:#e0f2fe,stroke:#0284c7,stroke-width:2px;
    classDef dag fill:#f3e8ff,stroke:#9333ea,stroke-width:2px;
    classDef storage fill:#fef3c7,stroke:#d97706,stroke-width:2px;

    class API,AF trigger;
    class T1,T2,T3,T4,T5 dag;
    class S3,OAI,DB storage;
```

---

## 2. DAG Topology & Dependency Graph

```mermaid
graph LR
    parse_pdf["parse_pdf\n(Layout & OCR)"]
    extract_facts["extract_facts\n(LLM Extraction)"]
    validate_facts["validate_facts\n(Sanity & Reconcile)"]
    calculate_kpis["calculate_kpis\n(KPI Recalculation)"]
    index_chunks["index_chunks\n(pgvector Embeddings)"]

    parse_pdf --> extract_facts
    extract_facts --> validate_facts
    validate_facts --> calculate_kpis
    parse_pdf --> index_chunks

    style parse_pdf fill:#eff6ff,stroke:#3b82f6,stroke-width:2px
    style extract_facts fill:#fdf4ff,stroke:#c026d3,stroke-width:2px
    style validate_facts fill:#fff7ed,stroke:#ea580c,stroke-width:2px
    style calculate_kpis fill:#f0fdf4,stroke:#16a34a,stroke-width:2px
    style index_chunks fill:#f5f3ff,stroke:#7c3aed,stroke-width:2px
```

- **Branch A (Structured Ledger Pipeline)**: `parse_pdf` &rarr; `extract_facts`
  &rarr; `validate_facts` &rarr; `calculate_kpis`
- **Branch B (Unstructured Semantic Search Pipeline)**: `parse_pdf` &rarr;
  `index_chunks` (executes in parallel with Branch A).

---

## 3. End-to-End Execution Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant API as FastAPI Backend
    participant AF as Airflow (Scheduler/Workers)
    participant MinIO as MinIO Storage
    participant OpenAI as OpenAI API
    participant DB as PostgreSQL (DB & pgvector)

    User->>API: POST /documents/upload (PDF filing)
    API->>MinIO: Upload raw PDF to S3 path
    API->>DB: Insert Document record (status="PROCESSING")
    API->>AF: POST /api/v1/dags/financial_ingestion_dag/dagRuns
    AF-->>API: 201 Created (dag_run_id)
    API-->>User: Upload Response (document_id, dag_run_id)

    rect rgb(240, 248, 255)
        Note over AF,MinIO: Task 1: parse_pdf
        AF->>MinIO: Download PDF bytes
        AF->>AF: PyMuPDF Layout Parsing (blocks, bboxes, headings)
        AF->>MinIO: Upload rendered page images (pages/{doc_id}/page_{n}.png)
        opt Text length < 100 chars (Scanned page)
            AF->>OpenAI: Vision OCR fallback (gpt-4o-mini)
            OpenAI-->>AF: OCR text blocks
        end
        AF->>AF: Push parsed layout to XCom (parsed_data)
    end

    par Parallel Execution: Extraction & Indexing
        rect rgb(253, 244, 255)
            Note over AF,OpenAI: Task 2: extract_facts
            AF->>DB: Fetch Document metadata (fiscal_year, period)
            AF->>OpenAI: Instructor structured extraction (gpt-4o-mini)
            OpenAI-->>AF: ExtractedFact List (concept, value, unit, location_id)
            AF->>DB: Insert SourceLocation & FinancialFactVersion (origin="AI_GENERATED")
            AF->>AF: Push summary to XCom (extraction_result)
        end
    and
        rect rgb(245, 243, 255)
            Note over AF,DB: Task 5: index_chunks
            AF->>AF: Filter TOC/Cover pages & split text into chunks (1000 chars, 150 overlap)
            AF->>OpenAI: Embeddings API (text-embedding-3-small)
            OpenAI-->>AF: 1536-dimensional embedding vectors
            AF->>DB: Insert DocumentChunk records with pgvector embeddings
        end
    end

    rect rgb(255, 247, 237)
        Note over AF,DB: Task 3: validate_facts
        AF->>DB: Query active facts for current & historical periods
        AF->>AF: Run Accounting Consistency & Balance Sheet Invariants
        AF->>AF: Run Sanity Checks (Negative revenue/cash, extreme margins)
        AF->>AF: Run Prior-Year Document Reconciliation Checks
        AF->>DB: Insert DataQualityIssue records (ERROR/WARNING)
    end

    rect rgb(240, 253, 244)
        Note over AF,DB: Task 4: calculate_kpis
        AF->>DB: Sync Metric Registry definitions
        AF->>DB: Query current & prior-year active facts
        AF->>AF: Execute Metric Formulas (Leverage, Profitability, Liquidity, Coverage)
        AF->>DB: Upsert DerivedMetricValue records
        AF->>DB: Establish Lineage links in derived_metric_input_facts
    end
```

---

## 4. Detailed Task Business Logic

### Task 1: `parse_pdf`

- **Source Module**: [`tasks/parsing.py`](./tasks/parsing.py)
- **Trigger Input (`dag_run.conf`)**:
  - `document_id`: Integer ID of the uploaded filing.
  - `company_id`: Integer ID of the company.
  - `s3_path`: MinIO path where the raw PDF is stored.
- **Core Logic**:
  1. **PDF Download**: Fetches PDF binary stream from MinIO via
     `StorageService.download_file`.
  2. **Page-by-Page Rendering**: Converts each page to a 150 DPI PNG image and
     uploads it to MinIO (`pages/{document_id}/page_{page_num}.png`) for the
     frontend interactive PDF viewer.
  3. **Text & Layout Extraction**: Extracts text blocks with bounding boxes
     `(x0, y0, x1, y1)` using PyMuPDF (`fitz`).
  4. **Noise Filtering**: Automatically removes running headers and footers by
     ignoring content in the top 5% (`y0 < height * 0.05`) and bottom 5%
     (`y1 > height * 0.95`).
  5. **Displayed Page Number Extraction**: Regex scans bottom 10% for Roman
     numerals or printed page digits (e.g., `Page 12`, `iv`).
  6. **Heading & Section Path Tracking**: Detects section markers (`Item 1`,
     `Part II`, `Note 3`) and bold/larger fonts to build a hierarchical
     breadcrumb (`Item 1. Business > Financial Statements`).
  7. **OCR Fallback**: If a page contains `< 100` selectable characters (scanned
     / image PDF), base64 encodes the page image and calls OpenAI Vision
     (`gpt-4o-mini`) to extract textual blocks.
- **Task Output (XCom)**:
  ```json
  {
    "document_id": 1,
    "company_id": 1,
    "pages": [
      {
        "page_number": 1,
        "displayed_page_number": "1",
        "section_path": "Item 8. Financial Statements > Note 1",
        "blocks": [
          {
            "id": "p1_b0",
            "text": "Total Revenue was $1,250M...",
            "bbox": [54.0, 120.5, 500.0, 140.0]
          }
        ]
      }
    ]
  }
  ```

---

### Task 2: `extract_facts`

- **Source Module**: [`tasks/extraction.py`](./tasks/extraction.py)
- **Core Logic**:
  1. **Document Context**: Retrieves `fiscal_year` and `fiscal_period` from the
     `Document` database record.
  2. **Prompt Assembly**: Formats extracted text blocks annotated with
     `[Block ID: px_by]` and `[Section: ...]`.
  3. **Structured LLM Extraction**: Uses `instructor` with OpenAI `gpt-4o-mini`
     and Pydantic schemas (`ExtractedFactsList`) to extract canonical financial
     concepts:
     - _Canonical Concepts_: `Revenue`, `Cost of Goods Sold`, `Gross Profit`,
       `Operating Income`, `EBITDA`, `Net Income`, `Total Debt`, `Cash`,
       `Current Assets`, `Current Liabilities`, `Total Equity`,
       `Operating Cash Flow`, `Capital Expenditures`, `Total Assets`,
       `Total Liabilities`, `Interest Expense`, `Short-term Debt`,
       `Long-term Debt`, `Working Capital`, `Free Cash Flow`.
     - Scales units automatically (e.g., converts `"$1.2B"` to `1200000000.0`).
  4. **Database Persistence & Versioning**:
     - **`SourceLocation`**: Saves exact bounding box, page number, section
       breadcrumb, and SHA-256 hash of text snippet.
     - **`FinancialFact`**: Maps
       `(company_id, concept, fiscal_year, fiscal_period)`.
     - **`FinancialFactVersion`**: Deactivates older active versions
       (`is_current = False`), increments `version`, sets
       `origin = "AI_GENERATED"`, `verification_status = "UNVERIFIED"`, and
       links to the `SourceLocation`.
- **Task Output (XCom)**:
  ```json
  {
    "document_id": 1,
    "company_id": 1,
    "fiscal_year": 2025,
    "fiscal_period": "FY",
    "fact_ids": [101, 102, 103, 104]
  }
  ```

---

### Task 3: `validate_facts`

- **Source Module**: [`tasks/validation.py`](./tasks/validation.py)
- **Core Logic**:
  1. **Fetches Active Facts**: Loads all current `FinancialFactVersion` records
     for the company across target and historical periods.
  2. **Mathematical Consistency Checks (Accounting Rules)**:
     - $\text{Gross Profit} \equiv \text{Revenue} - \text{COGS}$
     - $\text{Operating Income} \equiv \text{Gross Profit} - \text{Operating Expense}$
     - $\text{Total Assets} \equiv \text{Total Liabilities} + \text{Total Equity}$
     - $\text{Free Cash Flow} \equiv \text{Operating Cash Flow} - \text{Capital Expenditures}$
     - $\text{Total Debt} \equiv \text{Short-term Debt} + \text{Long-term Debt}$
     - $\text{Working Capital} \equiv \text{Current Assets} - \text{Current Liabilities}$
     - _Tolerance_: Any discrepancy $> 1.0$ generates a `DataQualityIssue`
       (`severity="ERROR"`, `issue_type="ACCOUNTING_RULE_VIOLATION"`).
  3. **Financial Sanity Checks**:
     - Flags negative Revenue, negative Cash, negative Total Assets, or negative
       Total Debt (`severity="WARNING"`, `issue_type="SANITY_CHECK_WARNING"`).
     - Validates Gross Margin $\in [-100\%, 100\%]$.
  4. **Prior-Year Reconciliation Checks**:
     - Compares reported prior-year numbers in the current document against
       historical documents already registered in the workstation. Discrepancies
       generate `issue_type="RECONCILIATION_DISCREPANCY"`.

---

### Task 4: `calculate_kpis`

- **Source Module**:
  [`apps/api/src/api/services/metric_calculation.py`](/apps/api/src/api/services/metric_calculation.py)
- **Core Logic**:
  1. **Registry Synchronization**: Synchronizes formulas and definitions from
     [`METRIC_REGISTRY`](/apps/api/src/api/core/metric_registry.py) into
     `derived_metric_definitions`.
  2. **Fact Aggregation**: Assembles current and prior-year normalized facts
     into calculation vectors.
  3. **Deterministic Metric Computations**:
     - **Profitability**: Gross Margin, EBITDA Margin, Operating Margin, Net
       Profit Margin.
     - **Leverage & Debt**: Total Debt, Net Debt, Debt-to-EBITDA, Net
       Debt-to-EBITDA, Debt-to-Capital.
     - **Liquidity**: Current Ratio, Quick Ratio, Cash Ratio, Working Capital.
     - **Coverage & Cash Flow**: EBITDA-to-Interest, EBIT-to-Interest,
       FCF-to-Debt, Cash Flow-to-Interest.
     - **Growth**: YoY Revenue Growth (compares with $FY_{t-1}$).
  4. **Relational Lineage Tracking**:
     - Upserts snapshot values into `derived_metric_values`.
     - Populates `derived_metric_input_facts` with exact references to the
       `FinancialFactVersion` records and input roles (`INPUT`, `PRIOR_PERIOD`,
       `SHORT_TERM_DEBT`, etc.), enabling zero-duplication audit trails and
       click-to-source UI navigation.

---

### Task 5: `index_chunks` (Parallel Branch)

- **Source Module**: [`tasks/indexing.py`](./tasks/indexing.py)
- **Core Logic**:
  1. **Irrelevant Page Filtering**: Skips Tables of Contents and Cover pages
     using heuristic pattern matching.
  2. **Sliding-Window Chunking**: Chunks text into 1,000-character segments with
     150-character overlap.
  3. **Section Path Annotation**: Prepends section breadcrumbs
     (`Section: Item 8 > Note 1...`) to prevent embedding semantic drift.
  4. **Concept & Metric Tagging**: Identifies mentioned financial concepts and
     tags affected metrics in `chunk_metadata`.
  5. **Vector Embedding**: Calls OpenAI `text-embedding-3-small` (1536
     dimensions).
  6. **Vector Store Persistence**: Inserts into `document_chunks` table
     utilizing PostgreSQL `pgvector` for semantic search and RAG citations.

---

## 5. DAG Configuration & Environment Variables

| Variable                              | Description                                               | Default / Example               |
| :------------------------------------ | :-------------------------------------------------------- | :------------------------------ |
| `AIRFLOW_URL`                         | Base URL of Airflow webserver                             | `http://airflow-webserver:8080` |
| `OPENAI_API_KEY`                      | OpenAI API key for OCR, extraction, and embeddings        | `sk-...`                        |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` | PostgreSQL credentials                                    | `underwriter` / `...`           |
| `POSTGRES_DB`                         | Application database with pgvector extension              | `credit_underwriting`           |
| `MINIO_ENDPOINT`                      | MinIO S3 endpoint                                         | `minio:9000`                    |
| `MINIO_BUCKET_NAME`                   | Storage bucket for uploaded PDFs and rendered page images | `financial-documents`           |

---

## 6. Running & Testing Pipelines Locally

### Triggering via Airflow CLI (Inside Docker container)

```bash
docker exec -it airflow-webserver airflow dags trigger financial_ingestion_dag \
  --conf '{"document_id": 1, "company_id": 1, "s3_path": "uploads/company_1/doc_1.pdf"}'
```

### Running Pipeline Unit Tests

```bash
# Run task test suite
pytest apps/pipelines/tests/
```
