# Analyst Frontend Architecture & Data Flow Documentation

This document provides a comprehensive technical overview of the Analyst UI
frontend architecture, its **Model-View-Controller (MVC)** design pattern, its
relationship to the backend database schema, and detailed sequence diagrams for
every core logical workflow.

---

## 1. High-Level System Architecture

The application is structured as a decoupled full-stack platform:

- **Database Layer**: PostgreSQL storing relational entities (companies,
  filings, facts, versions, calculated metrics, audit trails, and vector
  embeddings).
- **Service & API Layer**: FastAPI exposing RESTful endpoints for metric
  calculation, fact mutations, evidence lineage, and Airflow orchestration.
- **Frontend Layer**: React 18 + TypeScript + TailwindCSS + Recharts, structured
  strictly around the **Model-View-Controller (MVC)** design pattern.

```mermaid
flowchart TB
    subgraph DatabaseLayer["Database Layer (PostgreSQL)"]
        DB_Comp[(companies)]
        DB_Docs[(documents / source_locations)]
        DB_Facts[(financial_facts / versions)]
        DB_Metrics[(derived_metric_values / input_links)]
        DB_Audit[(audit_events)]
    end

    subgraph BackendAPI["Backend Service Layer (FastAPI)"]
        API_Endpoints["REST Endpoints (/api/...)"]
        MetricCalc["MetricCalculationService\n(Deterministic Rules & Lineage)"]
        AirflowSvc["AirflowService\n(DAG Trigger & Task Polling)"]
    end

    subgraph FrontendMVC["Frontend Architecture (MVC)"]
        subgraph Models["Models (Domain Entities & Utilities)"]
        M_Comp["company.ts (Company, Rating Rules)"]
        M_Metric["metric.ts (MetricItem, Lineage, Formatters)"]
        M_Fact["fact.ts (FinancialFact, Correction Schemas)"]
        M_Pipe["pipeline.ts (PipelineJob, Task Steps)"]
        end

        subgraph Controllers["Controllers (State Hooks & API Clients)"]
        C_API["apiClient.ts (REST Fetch Client)"]
        C_Comp["useCompanyController"]
        C_Metric["useMetricsController"]
        C_Fact["useFactsController"]
        C_Pipe["usePipelineController"]
        end

        subgraph Views["Views (Presentational & Compound Components)"]
        V_Banner["CompanyBanner.tsx"]
        V_Tabs["KPICategoryTabs.tsx"]
        V_Grid["KPIGrid.tsx / KPICard.tsx"]
        V_Drawer["KPIDetailDrawer.tsx"]
        V_Modal["DataCorrectionModal.tsx"]
        V_Copilot["CopilotPanel.tsx"]
        V_Upload["UploadView.tsx"]
        V_Dash["DashboardView.tsx"]
        end

        App["App.tsx (Root Layout & MVC Coordinator)"]
    end

    DB_Comp <--> API_Endpoints
    DB_Docs <--> API_Endpoints
    DB_Facts <--> API_Endpoints
    DB_Metrics <--> MetricCalc <--> API_Endpoints
    DB_Audit <--> API_Endpoints

    API_Endpoints <--> C_API
    C_API <--> Controllers
    Controllers <--> App <--> Views
    Models -. Type Definitions & Utilities .-> Controllers
    Models -. Pure Formatting & Ratings .-> Views
```

---

## 2. Database Schema to Frontend Model Mapping

The frontend models in [`apps/analyst_ui/src/models/`](./src/models) directly
reflect the database schema while decoupling presentation logic from raw table
structures.

```mermaid
erDiagram
    COMPANIES ||--o{ DOCUMENTS : "owns"
    COMPANIES ||--o{ FINANCIAL_FACTS : "has"
    COMPANIES ||--o{ DERIVED_METRIC_VALUES : "has calculated"
    DOCUMENTS ||--o{ SOURCE_LOCATIONS : "contains"
    DOCUMENTS ||--o{ DOCUMENT_CHUNKS : "chunked into"
    SOURCE_LOCATIONS ||--o{ FINANCIAL_FACT_VERSIONS : "evidence cited by"
    FINANCIAL_FACTS ||--o{ FINANCIAL_FACT_VERSIONS : "version history"
    DERIVED_METRIC_DEFINITIONS ||--o{ DERIVED_METRIC_VALUES : "defines"
    DERIVED_METRIC_VALUES ||--o{ DERIVED_METRIC_INPUT_FACTS : "relational lineage"
    FINANCIAL_FACT_VERSIONS ||--o{ DERIVED_METRIC_INPUT_FACTS : "constituent input"

    COMPANIES {
        int id PK
        string name
        string ticker
        string industry
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
        int source_location_id FK
        boolean is_current
    }
    DERIVED_METRIC_VALUES {
        int id PK
        int company_id FK
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
```

### Mapping Table: Database to Frontend Types

| Database Table(s)                                                                | Backend REST Response                             | Frontend Model / Interface                                                                    | Purpose in UI                                                                                      |
| :------------------------------------------------------------------------------- | :------------------------------------------------ | :-------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------- |
| `companies`, `financial_facts`                                                   | `CompanyResponse`, `CompanySummaryResponse`       | [`Company`](./src/models/company.ts), [`CompanySummary`](./src/models/company.ts)             | Header company switcher, credit rating badge (`BB`, `A`, `B`), verified data quality %.            |
| `derived_metric_values`, `derived_metric_definitions`                            | `CompanyMetricResponse`                           | [`MetricItem`](./src/models/metric.ts), [`MetricHistoryPoint`](./src/models/metric.ts)        | KPI cards, YoY deltas, category tabs, sparkline charts.                                            |
| `derived_metric_input_facts`, `source_locations`, `documents`, `document_chunks` | `MetricLineageResponse`                           | [`MetricLineage`](./src/models/metric.ts), [`MetricInputFactLineage`](./src/models/metric.ts) | KPI detail drawer: multi-year chart, formula breakdown, page/section source citations, RAG chunks. |
| `financial_facts`, `financial_fact_versions`                                     | `FinancialFactResponse`, `FactCorrectionResponse` | [`FinancialFact`](./src/models/fact.ts), [`FactCorrectionPayload`](./src/models/fact.ts)      | Data Correction Modal, analyst override audit justification, verified fact list.                   |

---

## 3. Low-Level Logical Workflows (Sequence Diagrams)

### Workflow 1: Initial Page Load & Dynamic KPI Hydration

When the analyst opens the application or selects a company from the top
navigation dropdown:

```mermaid
sequenceDiagram
    autonumber
    actor Analyst
    participant Header as Header View
    participant App as App (Coordinator)
    participant C_Comp as useCompanyController
    participant C_Metric as useMetricsController
    participant API as FastAPI Backend
    participant MetricSvc as MetricCalculationService
    participant DB as PostgreSQL DB
    participant UI as DashboardView / KPIGrid

    Analyst->>Header: Selects Company (e.g., Acme Corp ID: 1)
    Header->>App: onSelectCompany(1)
    App->>C_Comp: setSelectedCompanyId(1)
    App->>C_Metric: Instantiated with companyId = 1

    C_Metric->>API: GET /api/companies/1/metrics
    API->>DB: Query FinancialFacts & DerivedMetricValues for Company 1
    alt Metrics not yet calculated or facts updated
        API->>MetricSvc: recalculate_metrics_for_period(1, 2026, "FY26")
        MetricSvc->>DB: Query current FinancialFactVersions
        MetricSvc->>MetricSvc: Compute Formulas (EBITDA, Net Debt / EBITDA, Coverage, etc.)
        MetricSvc->>DB: Upsert DerivedMetricValue snapshot & InputFact links
    end
    API-->>C_Metric: Returns List[CompanyMetricResponse] (current_val, prior_val, YoY, history)
    
    C_Metric->>App: Updates `metrics` state
    App->>C_Comp: Evaluates rating rules (netDebtEbitda, interestCoverage, currentRatio)
    C_Comp->>UI: Hydrates CompanyBanner (Rating: "BB", Risk: "Elevated", Quality: 92%)
    C_Metric->>UI: Renders KPIGrid with formatted values, trend arrows, and sparklines
```

---

### Workflow 2: KPI Detail Inspection & Evidence Provenance

When an analyst clicks any KPI card on the dashboard to inspect the audit trail
and mathematical breakdown:

```mermaid
sequenceDiagram
    autonumber
    actor Analyst
    participant KPICard as KPICard View
    participant C_Metric as useMetricsController
    participant Drawer as KPIDetailDrawer View
    participant API as FastAPI Backend
    participant DB as PostgreSQL DB

    Analyst->>KPICard: Clicks on "Net Debt / EBITDA"
    KPICard->>C_Metric: setSelectedMetric(metric)
    C_Metric->>Drawer: Opens Drawer with metric header & historical Recharts AreaChart
    C_Metric->>API: GET /api/metrics/{derived_metric_id}/lineage
    
    API->>DB: Query DerivedMetricValue with JoinedLoad:
    Note over DB: Joins derived_metric_input_facts ->\nfact_versions -> financial_facts ->\nsource_locations -> documents -> chunks
    DB-->>API: Relational Lineage Graph
    API-->>C_Metric: Returns MetricLineageResponse

    C_Metric->>Drawer: Updates `lineage` state
    Drawer->>Drawer: Renders Deterministic Formula: "€840M / €178M = 4.72x"
    Drawer->>Drawer: Renders Input Facts (Total Debt: €840M, EBITDA: €178M)
    Drawer->>Drawer: Renders Document Source Citation: "Annual Report 2026 · Page 42 · Balance Sheet"
    Drawer->>Drawer: Renders Extracted Text Snippet & Bounding Box
```

---

### Workflow 3: Fact Correction & Synchronous Recalculation

When an analyst identifies an incorrect AI-extracted fact and submits an
override with an audit reason:

```mermaid
sequenceDiagram
    autonumber
    actor Analyst
    participant Drawer as KPIDetailDrawer View
    participant Modal as DataCorrectionModal View
    participant C_Fact as useFactsController
    participant C_Metric as useMetricsController
    participant API as FastAPI Backend
    participant MetricSvc as MetricCalculationService
    participant DB as PostgreSQL DB

    Analyst->>Drawer: Clicks "Correct" on Revenue fact (€2.0M -> should be €1.5M)
    Drawer->>Modal: Opens modal with selected fact (€2.0M)
    Analyst->>Modal: Types "1.5M" and Reason: "Adjusted for discontinued operations"
    Analyst->>Modal: Clicks "Save Correction"
    
    Modal->>C_Fact: correctFact(factId, value=1500000, reason="...")
    C_Fact->>API: POST /api/facts/{fact_id}/correct {value: 1500000, change_reason: "..."}
    
    API->>DB: 1. Deactivate old FinancialFactVersion (is_current = False)
    API->>DB: 2. Insert new FinancialFactVersion (v2, value=1500000, origin="ANALYST_CORRECTED", verification_status="VERIFIED")
    API->>DB: 3. Insert AuditEvent record (actor="analyst", old="2000000", new="1500000")
    API->>DB: Commit Fact Version & Audit Trail

    API->>MetricSvc: 4. Synchronously trigger recalculate_metrics_for_period()
    MetricSvc->>DB: Recompute affected formulas with new €1.5M fact
    MetricSvc->>DB: Update DerivedMetricValue records & junction links
    
    API-->>C_Fact: Returns FactCorrectionResponse (fact, affected_metrics: ["Revenue Growth", "Gross Margin", "EBITDA Margin", "Suggested Rating"])
    
    C_Fact->>Modal: Displays Post-Save Feedback (New verified value: €1.5M + Affected Metrics list)
    C_Fact->>C_Metric: Triggers handleDataUpdated() -> refreshMetrics()
    C_Metric->>API: GET /api/companies/{id}/metrics (Fetches fresh recalculated metrics)
    API-->>C_Metric: Returns updated metric snapshots
    C_Metric->>Drawer: Synchronously updates open lineage and KPI grid without reload
```

---

### Workflow 4: Direct Fact Verification

When an analyst confirms that an AI-extracted fact matches the filing document:

```mermaid
sequenceDiagram
    autonumber
    actor Analyst
    participant Drawer as KPIDetailDrawer View
    participant C_Fact as useFactsController
    participant C_Metric as useMetricsController
    participant API as FastAPI Backend
    participant DB as PostgreSQL DB

    Analyst->>Drawer: Clicks "Verify" on fact (e.g., Total Debt)
    Drawer->>Drawer: Optimistically updates badge to "✓ Verified"
    Drawer->>C_Fact: onVerifyFact(factId)
    
    C_Fact->>API: POST /api/facts/{factId}/verify
    API->>DB: Update FinancialFactVersion (verification_status = "VERIFIED")
    API->>DB: Insert AuditEvent (action = "FACT_VERIFIED")
    API->>DB: Synchronous KPI recalculation & commit
    API-->>C_Fact: Returns updated FinancialFact
    
    C_Fact->>C_Metric: Triggers refreshMetrics()
    C_Metric->>Drawer: Re-fetches lineage; confirms verified state
```

---

### Workflow 5: Document Upload & Airflow Ingestion DAG

When an analyst uploads a new financial report PDF:

```mermaid
sequenceDiagram
    autonumber
    actor Analyst
    participant UploadUI as UploadView
    participant C_Pipe as usePipelineController
    participant API as FastAPI Backend
    participant Airflow as Apache Airflow DAG
    participant App as App (Coordinator)

    Analyst->>UploadUI: Drops filing PDF (e.g., Annual_Report_2026.pdf)
    UploadUI->>C_Pipe: handleUpload(file)
    C_Pipe->>C_Pipe: Adds job to state (state = "uploading")
    
    C_Pipe->>API: POST /api/upload (multipart/form-data)
    API->>API: Extract metadata (GPT-4o-mini: Company, Fiscal Year, Period)
    API->>API: Save Document to DB & upload PDF to MinIO storage
    API->>Airflow: Trigger DAG `financial_ingestion_dag`
    API-->>C_Pipe: Returns {document_id, dag_run_id, company, fiscal_year}
    
    C_Pipe->>C_Pipe: Updates job (state = "running", dag_run_id)
    
    loop Every 5 Seconds (Non-blocking Polling)
        C_Pipe->>API: GET /api/airflow/dag-runs/{dag_run_id}/tasks
        API->>Airflow: Query Airflow REST API for task instance states
        Airflow-->>API: Task States (parse_pdf, extract_facts, validate_facts, index_chunks, calculate_kpis)
        API-->>C_Pipe: Returns TaskStatus[]
        C_Pipe->>UploadUI: Updates live progress bar and task step indicators
    end
    
    Note over C_Pipe: When all tasks reach "success":
    C_Pipe->>C_Pipe: Mark job as "success"
    C_Pipe->>App: Callback triggers refreshCompanies(), refreshFacts(), refreshMetrics()
```

---

## 4. State Management Architecture in Frontend

All controllers are isolated custom React hooks acting as state machines. Their
coordination in [`App.tsx`](./src/App.tsx) maintains strict separation of
concerns:

```mermaid
graph TD
    subgraph Root["App.tsx Coordinator"]
        ActiveNavState["activeNav: 'dashboard' | 'upload'"]
        ActiveCompState["selectedCompanyId: number | null"]
    end

    subgraph StateHooks["MVC Controllers (State Machines)"]
        Hook_Comp["useCompanyController\n- companies[]\n- companySummary (Rating, Risk, Quality %)"]
        Hook_Metric["useMetricsController\n- metrics[]\n- filteredMetrics[]\n- selectedMetric\n- lineage (Audit & Sources)\n- refreshMetrics()"]
        Hook_Fact["useFactsController\n- facts[]\n- selectedFactForCorrection\n- correctionFeedback\n- verifyFact(), correctFact()"]
        Hook_Pipe["usePipelineController\n- jobs[]\n- activeJobCount\n- 5s polling interval"]
    end

    subgraph Views["Presentational Views"]
        V_Header["Header.tsx"]
        V_Dash["DashboardView.tsx"]
        V_Upload["UploadView.tsx"]
    end

    ActiveCompState --> Hook_Metric
    ActiveCompState --> Hook_Fact
    Hook_Metric -. metrics .-> Hook_Comp
    Hook_Fact -. facts .-> Hook_Comp

    Hook_Fact -. onFactsUpdated callback .-> Hook_Metric
    Hook_Pipe -. onPipelineCompleted callback .-> Hook_Comp
    Hook_Pipe -. onPipelineCompleted callback .-> Hook_Fact
    Hook_Pipe -. onPipelineCompleted callback .-> Hook_Metric

    Hook_Comp --> V_Header
    Hook_Pipe --> V_Header
    Hook_Comp --> V_Dash
    Hook_Metric --> V_Dash
    Hook_Fact --> V_Dash
    Hook_Pipe --> V_Upload
```

---

## 5. Directory Structure Summary

```text
apps/analyst_ui/src/
├── models/
│   ├── company.ts             # Company interfaces, data quality, & credit rating evaluation rules
│   ├── metric.ts              # MetricItem, Lineage, Categories, formatMetricValue, parseAnalystInput
│   ├── fact.ts                # FinancialFact, FactCorrectionPayload, FactCorrectionResult
│   └── pipeline.ts            # PipelineJob, TaskStatus, TASK_STEPS definition
├── controllers/
│   ├── apiClient.ts           # Type-safe fetch wrapper with error boundary support
│   ├── useCompanyController.ts# Portfolio company state & underwriting risk scoring
│   ├── useMetricsController.ts# Dynamic metric fetching, category filtering & lineage retrieval
│   ├── useFactsController.ts  # Fact verification, correction overrides & affected metric feedback
│   └── usePipelineController.ts# Asynchronous filing upload & 5s Airflow DAG polling
├── views/
│   ├── components/
│   │   ├── Header.tsx         # Top bar with company switcher & active ingestion badge
│   │   ├── CompanyBanner.tsx  # Dynamic hero banner (Rating, Risk Level, Quality Score)
│   │   ├── KPICategoryTabs.tsx# Category navigation strip (Overview + 6 financial pillars)
│   │   ├── KPICard.tsx        # KPI card with sparklines, YoY directional badge, & formatted values
│   │   ├── KPIGrid.tsx        # Responsive grid layout with loading skeletons
│   │   ├── KPIDetailDrawer.tsx# Provenance drawer: Recharts trend, formula, and source citations
│   │   ├── DataCorrectionModal.tsx # Fact override modal with real business logic feedback
│   │   └── CopilotPanel.tsx   # Underwriting Copilot sidebar with context grounding
│   ├── DashboardView.tsx      # Main underwriting analysis workspace
│   └── UploadView.tsx         # Drag & drop filing upload and Airflow DAG progress monitor
├── App.tsx                    # Root layout & MVC coordinator
└── main.tsx                   # React 18 DOM mount point
```
