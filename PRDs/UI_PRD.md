# UI Product Requirements Document (PRD)

## 1. Overview & Objectives

The Analyst Frontend is an interactive credit underwriting workbench. It enables financial analysts to review automated AI extractions from corporate filings (10-Ks, 10-Qs, Annual Reports), inspect deterministic credit metrics across 6 key financial categories, verify evidence provenance down to the exact source page and snippet, and perform analyst overrides with instant, synchronous recalculation of all derived financial KPIs.

### Key Goals:
1. **Dynamic Metric Visualization**: Replace all static dummy data with dynamic records loaded from the backend API.
2. **Model-View-Controller (MVC) Pattern**: Structure the frontend cleanly into decoupled Models (types & business logic), Controllers (API integration & reactive state management), and Views (pure presentation components).
3. **Full Evidence Provenance (Lineage)**: Transparently show formula calculations, input facts, source document links, and exact page references.
4. **Interactive Data Correction UX**: Provide real business logic for verifying and correcting `FinancialFactVersion` records, triggering synchronous backend KPI recalculations and showing affected metric feedback.
5. **Real-time Pipeline Tracker**: Non-blocking filing upload with live 5-second polling of Airflow DAG task states (`parse_pdf` -> `extract_facts` / `index_chunks` -> `validate_facts` -> `calculate_kpis`).
6. **Credit Underwriting Copilot Integration**: Context-aware assistant panel ready for RAG and citation browsing.

---

## 2. Architecture & Frontend Structure

The application follows the **Model-View-Controller (MVC)** architectural pattern:

```text
apps/analyst_ui/src/
├── models/                     # [Model] Domain interfaces, calculation & formatting helpers
│   ├── company.ts             # Company metadata, credit rating & quality calculation rules
│   ├── metric.ts              # Metric definitions, historical time-series & lineage models
│   ├── fact.ts                # Financial fact versions, verification status & correction schemas
│   └── pipeline.ts            # Pipeline job execution states & DAG task steps
├── controllers/                # [Controller] Reactive hooks, state machines & API services
│   ├── apiClient.ts           # Centralized API fetch client with error handling
│   ├── useCompanyController.ts# Manages active company state, list & quality issues
│   ├── useMetricsController.ts# Manages metric loading, category tabs, YoY deltas & lineage
│   ├── useFactsController.ts  # Manages fact verification, correction mutations & affected metrics
│   └── usePipelineController.ts# Manages filing uploads & live Airflow status polling
├── views/                      # [View] Presentation components & page layouts
│   ├── components/
│   │   ├── Header.tsx         # Top bar with company switcher, status badge & navigation
│   │   ├── CompanyBanner.tsx  # Hero summary with rating, risk, filing & data quality metrics
│   │   ├── KPICategoryTabs.tsx# Tab strip for 6 financial categories + Overview
│   │   ├── KPIGrid.tsx        # Responsive grid layout for KPI cards
│   │   ├── KPICard.tsx        # Metric card with current value, YoY change & sparkline
│   │   ├── KPIDetailDrawer.tsx# Side drawer for deep metric inspection & calculation lineage
│   │   ├── DataCorrectionModal.tsx # Modal for verifying or overriding financial facts
│   │   └── CopilotPanel.tsx   # Underwriting AI assistant sidebar with context injection
│   ├── DashboardView.tsx      # Main underwriting dashboard view
│   └── UploadView.tsx         # Filing upload dropzone & pipeline tracking view
├── App.tsx                    # Top-level application router & layout orchestrator
└── main.tsx                   # React root entrypoint
```

---

## 3. Detailed UI Specifications

### 3.1 Company Header Banner
Displays real-time corporate status:
- **Company Name & Ticker**: With company switching dropdown selector.
- **Suggested Rating & Risk**: Deterministically derived credit rating (e.g. `BB`, `Elevated Risk`).
- **Primary Filing**: Latest fiscal report (e.g. `FY2025 Annual Report`).
- **Data Quality Score**: Percentage of verified facts (`XX% verified`) and count of active discrepancies / data quality issues requiring review.

### 3.2 KPI Category Tabs
Category navigation supporting:
- `Overview | Profitability | Leverage | Coverage | Liquidity | Cash Flow | Balance Sheet`

Each KPI card displays:
- Canonical display name (e.g., `Revenue`, `Net Debt / EBITDA`, `EBITDA Margin`)
- Current period value formatted by unit (Currency `€B/€M/€k`, Multiples `x`, Percentages `%`, Ratios)
- Prior period value and YoY change (`+0.83x YoY`, `+12% YoY`, `-4% YoY`)
- Directional trend indicator with risk-aware coloring (e.g., rising debt is red, rising EBITDA is green)
- Historical sparkline / mini trend chart (Recharts)
- Verification badge (`Verified`, `Corrected`, `AI-Generated / Unverified`, `Unavailable`)

### 3.3 KPI Detail Drawer (Provenance & Lineage)
Clicking any KPI opens a slide-over inspection drawer:
- **Title & Primary Metrics**: Latest year value and YoY delta.
- **Historical Performance**: 5-year historical trend chart (Recharts Area/Line chart) and data table.
- **Risk Interpretation**: Contextual analysis of leverage, coverage, or liquidity trajectory.
- **Formula & Computation**: Transparent formula breakdown with actual values (e.g. `€840m / €178m = 4.72x`).
- **Input Facts Breakdown**: Each constituent fact listed with its canonical concept, value, unit, and verification status.
- **Source Citations**: Exact document filename, filing year, section, and page number with highlight text snippet.
- **Fact Actions**: Quick action buttons to [Verify] or [Correct] constituent facts directly from the drawer.

### 3.4 Data Correction Workflow (Analyst Overrides)
Real business logic mutation on `FinancialFactVersion`:
1. Analyst inspects unverified AI-extracted fact (e.g., `EBITDA: €178M` from `Page 42`).
2. Analyst clicks **Verify** -> creates audit log and marks version as `VERIFIED`.
3. Or Analyst clicks **Correct** -> inputs new value (e.g., `€184M`) and mandatory audit reason (e.g. `Management adjusted EBITDA figure`).
4. System submits `POST /api/facts/{fact_id}/correct`:
   - Deactivates previous fact version (`is_current = false`).
   - Inserts new `FinancialFactVersion` (`origin = ANALYST_CORRECTED`, `verification_status = VERIFIED`).
   - Logs `AuditEvent`.
   - Synchronously triggers `MetricCalculationService.recalculate_metrics_for_period`.
5. Frontend displays feedback toast/banner showing the updated concept and all **Affected Metrics** that were recalculated:
   - `✓ EBITDA Margin`
   - `✓ Debt / EBITDA`
   - `✓ Net Debt / EBITDA`
   - `✓ Interest Coverage`
   - `✓ Suggested Rating`
6. Dashboard state refreshes automatically with recalculated figures.

### 3.5 Filing Ingestion & Pipeline Tracker
- **Dropzone**: Drag-and-drop or file browser for PDF filings with multi-file support.
- **Non-blocking Execution**: Triggers `/api/documents/upload` and receives `dag_run_id`.
- **Live Status Polling**: Polls `/api/pipeline/status/{dag_run_id}` every 5 seconds.
- **Topology Step Visualization**: Displays real-time progress across:
  - `parse_pdf`: Extract text, tables & page images
  - `extract_facts`: AI financial concept extraction
  - `index_chunks`: Vector embeddings to pgvector
  - `validate_facts`: Accounting rule consistency check
  - `calculate_kpis`: Derive credit metrics

### 3.6 Credit Underwriting Copilot Workbench
An omnipresent assistant panel integrated globally across all screens:
- **Global Resizable Shell**:
  - Positioned as a persistent right drawer in `App.tsx` accessible on all views.
  - Interactive horizontal drag handle enabling the user to dynamically resize the panel width between `360px` and `800px` (ideal for inspecting detailed charts).
  - Quick-collapse and expand button with badge indicator.
- **Dynamic Context Pill**:
  - Displays currently ingested focus context at the top of the chat (e.g., `Focus: Acme Corp · Net Debt / EBITDA · 2 Input Facts (FY25 10-K & FY24 10-K)`).
  - Eagerly updates when the user switches company, clicks a KPI card, opens the detail drawer with its constituent facts, or navigates document pages. Supports multiple referenced facts and citations across multiple documents simultaneously.
- **Live Streaming & Human-Readable Reasoning**:
  - SSE real-time token streaming with animated progress chips displaying human-friendly backend step descriptions (`"Searching filing debt schedule..."`, `"Calculating 5-year historical coverage..."`, `"Building chart visualization..."`).
  - [Stop Generating] button to instantly cancel active stream via `AbortController`.
- **Generative UI Native Widgets**:
  - Renders native interactive Tailwind + Recharts visualization cards inline inside the chat stream:
    - **Line Charts**: Multi-metric time-series trends (e.g. EBITDA Margin vs Debt/EBITDA over time).
    - **Bar Charts**: Period-over-period or breakdown comparisons.
    - **Pie / Donut Charts**: Capital structure or debt composition.
    - **Word Cloud / Concept Frequency Cards**: Visualizing topical prominence across filings.
  - **Full-Screen Modal Overlay**: A dedicated maximize / expand button on every chart widget opens a full-screen overlay for deep exploration, presentation, and high-resolution inspection.
  - **Export Action**: High-resolution [Download PNG/SVG] action button on every chart widget (in-chat and in full-screen) for local use and presentation decks.
- **Grounded PDF Citation Navigation**:
  - Citations rendered as interactive badges (e.g., `[Annual Report 2025 · p. 42 (Debt Schedule)]`).
  - Clicking any citation opens the Document Preview drawer, scrolls directly to physical page index, and paints a highlight box over the referenced bounding box.
- **Multi-Session Management**:
  - Top action bar with [New Chat] button (resets conversation history and context).
  - Past conversations drawer enabling analysts to search and switch between historical chat sessions stored in PostgreSQL.

---

## 4. Error Handling & Edge States
- **Missing / Unavailable Metrics**: Explicitly display `N/A` with explanation reason (e.g. `Interest expense not reported in filing`). Never substitute zero.
- **API Disconnections**: Non-intrusive offline indicator with automatic retry.
- **Validation Warnings**: Highlight discrepancies visually with warning badges and actionable links to the source fact.
- **Malformed Widget Safeguard**: If an agent output contains malformed chart JSON, fallback gracefully to a tabular data view without crashing the UI.


