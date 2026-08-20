# AI-Assisted Credit Underwriting API Service

The `api` container (`credit-underwriting-api`) serves as the central orchestration backend for the AI-Assisted Credit Underwriting platform. Built with **FastAPI**, **SQLAlchemy**, and **Pydantic**, it acts as the primary coordination layer—stitching together client interfaces, relational & vector databases, S3 object storage, LLM inference services, and Airflow ingestion pipelines.

---

## 1. High-Level System Architecture & Component Stitching

The diagram below illustrates how the `api` container directly interacts with every other container and external service defined in [`docker-compose.yml`](../../docker-compose.yml).

```mermaid
flowchart TB
    subgraph Clients["Frontend Layer"]
        UI["🖥️ Analyst UI (React / Vite)\n:3001"]
    end

    subgraph CoreAPI["FastAPI Application (credit-underwriting-api :8000)"]
        Router["API Router (/api)"]
        MetaExtract["MetadataExtractionService\n(Instructor + gpt-4o-mini)"]
        MetricCalc["MetricCalculationService\n(Deterministic KPI Engine)"]
        StoreSvc["StorageService\n(Boto3 S3 Client)"]
        AirflowSvc["AirflowService\n(HTTPX REST Client)"]
        AlembicRunner["Alembic Migrations\n(Startup Lifespan)"]
    end

    subgraph DataStorage["Databases & Object Storage"]
        Postgres[("🗄️ PostgreSQL + pgvector\n(:5432 underwriting_db)\n- Relational Ledger\n- Fact Versions & Audit\n- 1536-dim Embeddings")]
        MinIO[("🪣 MinIO Object Storage\n(:9000 S3 API / :9001 Console)\n- Raw Filings PDF\n- Rendered Page PNGs")]
    end

    subgraph Orchestration["Pipeline Orchestration"]
        AirflowWS["⚙️ Airflow Webserver\n(:8080 REST API)"]
        AirflowSch["🔄 Airflow Scheduler\n(financial_ingestion_dag)"]
    end

    subgraph ExternalServices["External AI Services"]
        OpenAI["🧠 OpenAI API\n- gpt-4o-mini (Metadata)\n- text-embedding-3-small"]
    end

    %% UI to API
    UI <-->|"HTTP / REST / JSON\nCORS enabled"| Router

    %% Startup
    AlembicRunner -->|"Auto-run migrations\non startup (head)"| Postgres

    %% API Internal routing
    Router --> MetaExtract
    Router --> MetricCalc
    Router --> StoreSvc
    Router --> AirflowSvc

    %% Service connections
    MetaExtract <-->|"Extract company, year, period\n(first 3 pages)"| OpenAI
    StoreSvc <-->|"S3 API (boto3)\nUpload PDF / Download Pages"| MinIO
    AirflowSvc -->|"POST /api/v1/dags/.../dagRuns\n(Trigger Pipeline)"| AirflowWS
    AirflowSvc <-->|"GET /api/v1/dags/.../dagRuns/{id}\n(Poll Status)"| AirflowWS
    AirflowWS --- AirflowSch
    
    MetricCalc <-->|"Read/Write Facts, Metrics,\nand Relational Lineage"| Postgres
    Router <-->|"CRUD Companies, Documents,\nQuality Issues, Audit Events"| Postgres
    AirflowSch <-->|"Tasks read S3 & write\nextracted facts/chunks"| Postgres
    AirflowSch <-->|"Download PDFs / Upload PNGs"| MinIO

    classDef client fill:#dbeafe,stroke:#1d4ed8,stroke-width:2px;
    classDef api fill:#f3e8ff,stroke:#7e22ce,stroke-width:2px;
    classDef storage fill:#fef3c7,stroke:#b45309,stroke-width:2px;
    classDef airflow fill:#dcfce7,stroke:#15803d,stroke-width:2px;
    classDef ai fill:#ffe4e6,stroke:#be123c,stroke-width:2px;

    class UI client;
    class Router,MetaExtract,MetricCalc,StoreSvc,AirflowSvc,AlembicRunner api;
    class Postgres,MinIO storage;
    class AirflowWS,AirflowSch airflow;
    class OpenAI ai;
```

---

## 2. Container Stitching: How the API Integrates with `docker-compose.yml`

| Component in `docker-compose.yml` | Protocol & Port | API Integration Mechanism | API Role & Business Responsibilities |
| :--- | :--- | :--- | :--- |
| **`postgres`** (`pgvector/pgvector:pg16`) | TCP `5432` (`SQLAlchemy` / `psycopg2`) | `DATABASE_URL` connection pool with automatic Alembic migration on container startup | Stores relational domain models (`Company`, `Document`, `FinancialFact`, `FinancialFactVersion`, `DerivedMetricValue`, `DerivedMetricInputFact`, `DataQualityIssue`, `AuditEvent`) and pgvector embeddings (`DocumentChunk`). |
| **`minio`** (`minio/minio`) | HTTP `9000` (`boto3` S3 client) | `StorageService` configured via `S3_ENDPOINT_URL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Persists original PDF documents at `filings/{company_id}/{fiscal_year}_{fiscal_period}/...` and caches page rendered PNGs at `pages/{document_id}/page_{page_number}.png`. |
| **`airflow-webserver`** (`apps/pipelines`) | HTTP `8080` (`httpx` Basic Auth) | `AirflowService` calling Airflow 2.x REST API (`/api/v1/dags/financial_ingestion_dag/...`) | Triggers ingestion DAG runs asynchronously with run metadata (`document_id`, `company_id`, `s3_path`), and allows the UI to poll task execution states in real-time. |
| **`analyst-ui`** (`apps/analyst_ui`) | HTTP `8000` (FastAPI REST endpoints) | CORS-enabled JSON API exposing `/api/companies`, `/api/documents`, `/api/facts`, `/api/metrics`, `/api/pipeline` | Provides data backing for the interactive financial spread, PDF viewer with bounding boxes, metric lineage graphs, quality issue triage, and audit events. |
| **OpenAI API** (External) | HTTPS `443` (`instructor` + `openai`) | `MetadataExtractionService` configured via `OPENAI_API_KEY` | Performs zero-shot structured extraction on upload to detect company name, fiscal period, and document type from initial PDF pages. |

---

## 3. Core Business Logic Workflows

### Workflow 1: Intelligent Document Ingestion & Pipeline Handshake

When a credit analyst uploads a financial filing (e.g. 10-K or 10-Q PDF), the API handles validation, deduplication, LLM-based metadata resolution, object storage, and pipeline dispatching:

```mermaid
sequenceDiagram
    autonumber
    actor Analyst as 👤 Credit Analyst (UI)
    participant API as 🚀 FastAPI Backend (/api)
    participant OAI as 🧠 OpenAI (gpt-4o-mini)
    participant MinIO as 🪣 MinIO (S3 Storage)
    participant DB as 🗄️ PostgreSQL (underwriting_db)
    participant AF as ⚙️ Airflow REST API

    Analyst->>API: POST /api/documents/upload (PDF multipart)
    API->>API: 1. Calculate SHA-256 Content Hash
    API->>DB: 2. Check for duplicate content_hash
    alt Hash exists in DB
        DB-->>API: Existing Document record
        API-->>Analyst: Return existing document (bypass processing)
    else Hash is new
        API->>API: 3. Extract text from first 3 pages (PyMuPDF)
        API->>OAI: 4. Extract structured metadata (Instructor JSON Schema)
        OAI-->>API: ExtractedMetadata (company, fiscal_year, fiscal_period, document_type)
        API->>DB: 5. Find or create Company record
        API->>MinIO: 6. Upload PDF to `filings/{company_id}/{year}_{period}/{type}_{hash}.pdf`
        API->>DB: 7. Insert Document record (s3_path, fiscal_year, fiscal_period)
        API->>AF: 8. POST /api/v1/dags/financial_ingestion_dag/dagRuns (conf payload)
        AF-->>API: 201 Created (dag_run_id)
        API-->>Analyst: Return DocumentResponse (id, company_id, dag_run_id)
    end

    loop Frontend Polling
        Analyst->>API: GET /api/pipeline/status/{dag_run_id}
        API->>AF: GET /api/v1/dags/.../dagRuns/{dag_run_id}/taskInstances
        AF-->>API: Task instance states (parse_pdf, extract_facts, etc.)
        API-->>Analyst: Return DAG & Task states (running | success | failed)
    end
```

---

### Workflow 2: Financial Fact Versioning, Verification & Auditability

The platform enforces strict bi-temporal accounting integrity. Facts are never blindly overwritten; any analyst correction or confirmation generates an immutable audit record and increments the version counter:

```mermaid
stateDiagram-v2
    [*] --> AI_GENERATED: Airflow Task 2 (extract_facts)
    
    state AI_GENERATED {
        UNVERIFIED: Status: UNVERIFIED\nOrigin: AI_GENERATED\nVersion: 1
    }

    UNVERIFIED --> VERIFIED: Analyst clicks Verify\nPOST /api/facts/{id}/verify
    
    state VERIFIED {
        CONFIRMED: Status: VERIFIED\nOrigin: AI_GENERATED\nVersion: 1\nAudit: FACT_VERIFIED
    }

    UNVERIFIED --> ANALYST_CORRECTED: Analyst edits value\nPOST /api/facts/{id}/correct
    CONFIRMED --> ANALYST_CORRECTED: Analyst amends value\nPOST /api/facts/{id}/correct

    state ANALYST_CORRECTED {
        OLD_DEACTIVATED: Old Version: is_current = false
        NEW_ACTIVE: New Version: is_current = true\nOrigin: ANALYST_CORRECTED\nStatus: VERIFIED\nVersion: N + 1\nAudit: FACT_CORRECTED
    }

    NEW_ACTIVE --> KPI_RECALC: Trigger Synchronous Recalculation
    CONFIRMED --> KPI_RECALC: Trigger Synchronous Recalculation
    
    state KPI_RECALC {
        RECOMPUTE: Recompute Derived Metrics\nUpdate Input Fact Lineage
    }
```

#### Key Rules:
1. **Current Version Constraint**: A partial unique index (`ix_fact_versions_current_uniq`) guarantees that exactly **one** version of a given `FinancialFact` can have `is_current = True` at any time.
2. **Audit Logging**: Every mutation creates an `AuditEvent` recording `actor`, `action`, `previous_value`, `new_value`, `reason`, and timestamp.
3. **Reactive Recomputation**: When a fact is verified or corrected, `MetricCalculationService` immediately runs in the same request cycle to update all affected KPIs.

---

### Workflow 3: Deterministic Derived KPI Engine & Relational Lineage

Derived metrics are computed deterministically based on canonical accounting rules defined in [`METRIC_REGISTRY`](./src/api/core/metric_registry.py).

```mermaid
flowchart LR
    subgraph Facts["Active Financial Facts (is_current=True)"]
        F1["Revenue ($1,250M)"]
        F2["COGS ($750M)"]
        F3["Operating Income ($250M)"]
        F4["Cash ($100M)"]
        F5["Total Debt ($400M)"]
        F6["EBITDA ($300M)"]
        F7["Prior Revenue ($1,000M)"]
    end

    subgraph Engine["MetricCalculationService"]
        Sync["1. Sync Metric Registry Definitions"]
        Calc["2. Compute Metric Formulas"]
        Lineage["3. Link Relational Lineage"]
    end

    subgraph Metrics["Derived Metric Outputs"]
        M1["Gross Margin: 40.0%"]
        M2["Operating Margin: 20.0%"]
        M3["Net Debt: $300M"]
        M4["Net Debt / EBITDA: 1.00x"]
        M5["YoY Revenue Growth: +25.0%"]
    end

    subgraph RelationalLineage["derived_metric_input_facts Table"]
        L1["Metric #4 &rarr; FactVersion (Total Debt, Role: INPUT)"]
        L2["Metric #4 &rarr; FactVersion (Cash, Role: INPUT)"]
        L3["Metric #4 &rarr; FactVersion (EBITDA, Role: DENOMINATOR)"]
    end

    Facts --> Engine
    Sync --> Calc --> Lineage
    Engine --> Metrics
    Lineage --> RelationalLineage
```

#### Metric Categories Supported:
- **Profitability**: Gross Margin, EBITDA Margin, Operating Margin, Net Profit Margin.
- **Leverage & Debt**: Total Debt, Net Debt, Debt-to-EBITDA, Net Debt-to-EBITDA, Debt-to-Capital.
- **Liquidity**: Current Ratio, Quick Ratio, Cash Ratio, Working Capital.
- **Coverage & Cash Flow**: EBITDA-to-Interest, EBIT-to-Interest, FCF-to-Debt, Cash Flow-to-Interest.
- **Growth & Performance**: YoY Revenue Growth (compares target year with $FY_{t-1}$).

---

### Workflow 4: PDF Page Serving & On-the-Fly Rendering Fallback

The API provides high-resolution rendered PNG images of document pages to the frontend viewer via `/api/documents/{id}/pages/{page_number}`:

```mermaid
flowchart TD
    Req["Analyst UI requests page image\nGET /api/documents/{id}/pages/{page}"] --> CheckMinIO{"Check MinIO Cache\n`pages/{doc_id}/page_{n}.png`"}
    
    CheckMinIO -- "Cache Hit (Found)" --> StreamCached["Stream cached PNG directly\n(Content-Type: image/png)"]
    
    CheckMinIO -- "Cache Miss (Not found)" --> FetchPDF["Download original PDF from MinIO\n`doc.s3_path`"]
    FetchPDF --> Render["Render Page on-the-fly\n(PyMuPDF / 150 DPI)"]
    Render --> CacheBack["Cache PNG to MinIO for future requests\n`pages/{doc_id}/page_{n}.png`"]
    CacheBack --> StreamRendered["Stream rendered PNG\n(Content-Type: image/png)"]

    classDef cacheHit fill:#dcfce7,stroke:#16a34a,stroke-width:2px;
    classDef cacheMiss fill:#fff7ed,stroke:#ea580c,stroke-width:2px;
    
    class StreamCached cacheHit;
    class FetchPDF,Render,CacheBack,StreamRendered cacheMiss;
```

---

## 4. Database Schema & Relational Models

The relational schema ensures full traceability from high-level credit metrics down to individual PDF character bounding boxes:

```mermaid
erDiagram
    COMPANIES ||--o{ DOCUMENTS : owns
    COMPANIES ||--o{ FINANCIAL_FACTS : has
    COMPANIES ||--o{ DERIVED_METRIC_VALUES : has
    COMPANIES ||--o{ DATA_QUALITY_ISSUES : flags
    COMPANIES ||--o{ DOCUMENT_CHUNKS : has

    DOCUMENTS ||--o{ SOURCE_LOCATIONS : contains
    DOCUMENTS ||--o{ DOCUMENT_CHUNKS : contains
    DOCUMENTS ||--o{ DATA_QUALITY_ISSUES : relates_to

    FINANCIAL_FACTS ||--o{ FINANCIAL_FACT_VERSIONS : tracks_versions
    FINANCIAL_FACT_VERSIONS }o--|| SOURCE_LOCATIONS : references_evidence

    DERIVED_METRIC_DEFINITIONS ||--o{ DERIVED_METRIC_VALUES : defines
    DERIVED_METRIC_VALUES ||--o{ DERIVED_METRIC_INPUT_FACTS : explains_lineage
    DERIVED_METRIC_INPUT_FACTS }o--|| FINANCIAL_FACT_VERSIONS : sourced_from

    COMPANIES {
        int id PK
        string name UK
        string ticker
        string industry
    }

    DOCUMENTS {
        int id PK
        int company_id FK
        string filename
        string s3_path
        string content_hash UK
        int fiscal_year
        string fiscal_period
        string document_type
    }

    SOURCE_LOCATIONS {
        int id PK
        int document_id FK
        int page_number
        string section_path
        text text_snippet
        jsonb bounding_box
    }

    FINANCIAL_FACTS {
        int id PK
        int company_id FK
        string concept
        int fiscal_year
        string fiscal_period
    }

    FINANCIAL_FACT_VERSIONS {
        int id PK
        int fact_id FK
        int version
        float value
        string unit
        string origin
        string verification_status
        boolean is_current
        int source_location_id FK
    }

    DERIVED_METRIC_DEFINITIONS {
        int id PK
        string metric_name UK
        string display_name
        string category
        string formula_expression
    }

    DERIVED_METRIC_VALUES {
        int id PK
        int company_id FK
        int metric_definition_id FK
        string metric_name
        float value
        string status
        int fiscal_year
        string fiscal_period
    }

    DERIVED_METRIC_INPUT_FACTS {
        int id PK
        int derived_metric_id FK
        int fact_version_id FK
        string concept_name
        string relationship_role
    }

    DOCUMENT_CHUNKS {
        int id PK
        int company_id FK
        int document_id FK
        int chunk_index
        text text_content
        vector embedding
    }
```

---

## 5. API Endpoint Reference

### Companies
| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/api/companies` | List all registered companies ordered by name. |
| `POST` | `/api/companies` | Register a new company with name and optional ticker. |
| `GET` | `/api/companies/{company_id}/quality-issues` | Retrieve unresolved accounting and reconciliation data quality issues. |

### Documents
| Method | Path | Description |
| :--- | :--- | :--- |
| `POST` | `/api/documents/upload` | Upload PDF filing, extract metadata via LLM, save to MinIO, and dispatch Airflow pipeline. |
| `GET` | `/api/documents/{document_id}` | Get metadata and status for a single document. |
| `GET` | `/api/documents/{document_id}/pages/{page_number}` | Stream high-res PNG image of a document page (MinIO cached or PyMuPDF rendered). |

### Financial Facts & Verification
| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/api/facts/{company_id}` | Retrieve all active financial facts (`is_current=True`) for a company. |
| `POST` | `/api/facts/{fact_id}/verify` | Mark fact version as `VERIFIED`, log audit event, and recalculate dependent KPIs. |
| `POST` | `/api/facts/{fact_id}/correct` | Deactivate old version, insert new `ANALYST_CORRECTED` version, log audit trail, and recalculate KPIs. |

### Derived Metrics & Lineage
| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/api/companies/{company_id}/metrics` | Retrieve all 6 categories of credit metrics with YoY deltas, trends, and history. |
| `GET` | `/api/metrics/{derived_metric_id}/lineage` | Retrieve full evidence lineage graph with exact input fact versions, formulas, and citations. |

### Pipeline Status & Copilot
| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/api/pipeline/status/{dag_run_id}` | Query Airflow DAG run state and individual task instance progress for UI polling. |
| `POST` | `/api/copilot/chat` | Credit Underwriting Copilot conversational assistant. |

---

## 6. Configuration & Environment Variables

| Variable | Description | Default in Docker Compose |
| :--- | :--- | :--- |
| `DATABASE_URL` | PostgreSQL SQLAlchemy connection string | `postgresql://postgres:postgres@postgres:5432/underwriting_db` |
| `POSTGRES_HOST` / `PORT` | Database host and port | `postgres` / `5432` |
| `POSTGRES_DB` | Application database name | `underwriting_db` |
| `MINIO_HOST` / `PORT` | MinIO server host and port | `minio` / `9000` |
| `S3_BUCKET` | Target S3 bucket for filings and page caches | `filings` |
| `AWS_ACCESS_KEY_ID` | MinIO root access key | `minioadmin` |
| `AWS_SECRET_ACCESS_KEY` | MinIO root secret key | `minioadmin` |
| `AIRFLOW_HOST` / `PORT` | Airflow webserver host and port | `airflow-webserver` / `8080` |
| `AIRFLOW_USERNAME` / `PASSWORD` | Airflow REST API authentication credentials | `admin` / `admin` |
| `OPENAI_API_KEY` | OpenAI API key for structured metadata extraction | `${OPENAI_API_KEY}` |

---

## 7. Running & Testing the API Locally

### Running with Docker Compose (Recommended)
```bash
docker-compose up api
```

### Running Locally with Uvicorn
```bash
cd apps/api
poetry run uvicorn api.app:app --host 0.0.0.0 --port 8000 --reload
```

### Running API Unit & Integration Tests
```bash
cd apps/api
pytest tests/
```
