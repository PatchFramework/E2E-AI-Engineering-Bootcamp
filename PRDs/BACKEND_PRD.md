# AI Copilot Backend Architecture & Tools

The Underwriting Copilot is implemented as an orchestrated **LangGraph Orchestrator-Subagent Graph** leveraging **LangSmith prompt versioning & tracing**, deterministic calculation tools, agentic hybrid pgvector retrieval, and validated Generative UI widget output.

## LangGraph Orchestrator-Subagent Architecture

```mermaid
flowchart TD
    User["Analyst Query + Ingested Context Snapshot"] --> Orchestrator["Orchestrator Agent (LangGraph Plan & Route)"]
    
    Orchestrator -->|Direct Answer / Greeting| DirectResponse["Direct Answer Synthesizer"]
    Orchestrator -->|Decompose Plan / Metrics| FinAgent["Financial Metric Sub-Agent"]
    Orchestrator -->|Filing Research / Risk Factors| DocAgent["Agentic RAG Sub-Agent"]
    Orchestrator -->|Accounting Reconciliations| QualAgent["Data Quality & Audit Sub-Agent"]
    
    FinAgent --> FinTools["SQL Facts + MetricCalculationService"]
    DocAgent --> RagTools["Agentic Hybrid Search (BM25 + pgvector)"]
    QualAgent --> QualTools["Data Quality Issues + Audit Events"]
    
    FinTools --> GenUIAgent["Generative UI Chart Sub-Agent"]
    RagTools --> GenUIAgent
    
    GenUIAgent --> WidgetValidator["Pydantic Chart Validator & Self-Correction Node"]
    
    FinTools --> Synthesis["Synthesis, Citations & Appendix Builder"]
    RagTools --> Synthesis
    QualTools --> Synthesis
    WidgetValidator --> Synthesis
    DirectResponse --> Synthesis
    
    Synthesis --> SSE["SSE Stream Output (Tokens + Status + Widgets + Citations)"]
```

## SSE Streaming Protocol
Endpoint: `POST /api/copilot/chat/stream`
Emits real-time event frames:
- `event: status` -> `{"step": "search", "message": "Searching FY2025 Debt Schedule for credit terms..."}`
- `event: token` -> `{"content": "Acme Corp reported net debt of €840M..."}`
- `event: widget` -> `{"widgetType": "chart", "spec": { ... validated Pydantic JSON ... }}`
- `event: citations` -> `[{"document_id": 2, "page_number": 42, "displayed_page": "p. 42", "bounding_box": [120, 340, 500, 480], "snippet": "..."}]`
- `event: trace` -> `{"run_id": "langsmith-run-uuid"}`
- `event: done` -> `{"session_id": "...", "message_id": "..."}`

---

# Copilot Tool Suite & Sub-Agent Schemas

All tools operate deterministically or through constrained SQL/pgvector queries with strict parameter injection (`company_id` is locked in graph state):

### 1. Financial Data & Deterministic Calculations (Financial Metric Sub-Agent)
```python
get_current_metric(company_id: int, metric_name: str, fiscal_year: Optional[int]) -> MetricValue
get_company_metrics(company_id: int, fiscal_year: Optional[int]) -> List[MetricValue]
get_metric_history(company_id: int, metric_name: str) -> List[HistoricalPoint]
get_fact_lineage(company_id: int, metric_name: str, fiscal_year: int) -> MetricLineage
calculate_custom_formula(expression: str, values: Dict[str, float]) -> CalculationResult
```

### 2. Agentic Hybrid Document Retrieval & Text Analytics (Agentic RAG Sub-Agent)
```python
search_filing_chunks_hybrid(
    query: str, 
    company_id: int, 
    fiscal_year: Optional[int] = None, 
    section_filter: Optional[str] = None, 
    dense_weight: float = 0.5,       # 1.0 = pure vector cosine, 0.0 = pure keyword BM25/tsvector
    keyword_query: Optional[str] = None,
    limit: int = 5                   # Agent dynamically tunes retrieval budget (1 to 15)
) -> List[GroundedChunkResult]

get_page_content(document_id: int, page_number: int) -> PageDetails
count_concept_frequency(company_id: int, terms: List[str], document_id: Optional[int] = None) -> Dict[str, int]
```

### 3. Data Quality & Audit Trail (Data Quality Sub-Agent)
```python
get_unverified_facts(company_id: int) -> List[UnverifiedFact]
get_data_quality_issues(company_id: int) -> List[QualityIssue]
get_fact_audit_trail(fact_id: int) -> List[AuditEvent]
```

### 4. Generative UI Widget Generator & Pydantic Validator Node (GenUI Sub-Agent)
```python
generate_chart_widget(
    chart_type: Literal["line", "bar", "pie", "word_cloud"],
    title: str,
    description: Optional[str],
    series: List[ChartSeriesConfig],
    data: List[Dict[str, Any]],
    unit: Optional[str]
) -> ChartWidgetPayload
```
* **Validation & Self-Correction Node**: Validates series keys, data keys, and palettes. If `ValidationError` is encountered, it is reflected back into the agent context for an immediate automatic 1-retry regeneration before failing to a table fallback.

### 5. Grounded Citation & Evidence Provenance Schema
```python
class CitationSource(BaseModel):
    document_id: int
    filename: str
    page_number: int
    displayed_page: str
    section: Optional[str] = None
    snippet: Optional[str] = None
    bounding_box: Optional[List[float]] = None
    confidence_score: Optional[float] = None
    source_type: Literal["FILING_CHUNK", "STRUCTURED_FACT", "AUDIT_EVENT"]
```
All sources retrieved by any sub-agent are automatically tracked in the graph state's `retrieved_sources` registry and appended to the final response envelope for analyst inspection.

---

# RAG Architecture (Agentic Hybrid Search)

RAG complements structured retrieval through an **Agentic Hybrid Retrieval** strategy:

```text
User question
      ↓
Intent understanding
      ↓
 ┌────┴─────────────┐
 ↓                  ↓
Structured        Document
retrieval         retrieval
 ↓                  ↓
Postgres          pgvector
 ↓                  ↓
 └───────┬──────────┘
         ↓
      Evidence
         ↓
       LLM
         ↓
Answer + citations
```

For:

> "Why did leverage increase?"

the agent should retrieve both:

- Net debt history
- EBITDA history
- debt changes
- relevant filing text explaining the change

---

# Vector Metadata

Every chunk should contain metadata such as:

```text
company_id
document_id
document_type
fiscal_year
fiscal_period
page
section
financial_concepts
kpis
source_type
language
```

Example:

```text
company_id = ACME
fiscal_year = 2025
section = Debt and Financing
kpis = [net_debt, liquidity, leverage]
page = 104
```

This enables filtered retrieval.

---

# Credit Rating Methodology

Use rating bands rather than a numeric score.

Example:

```text
AAA
AA
A
BBB
BB
B
CCC
```

The exact thresholds should be explicitly configurable.

For example:

```text
Net Debt / EBITDA
< 1.0x       → positive
1.0–2.0x     → strong
2.0–3.0x     → moderate
3.0–4.0x     → elevated
> 4.0x       → weak
```

Similar rules can be defined for:

- interest coverage
- liquidity
- FCF
- profitability
- debt trend

The rating engine produces:

```text
Suggested Rating: BB

Primary drivers:
- Elevated leverage
- Weakening interest coverage
- Negative FCF
- Adequate liquidity
```

The UI should explicitly say:

> **AI-assisted suggested rating — analyst judgment required**

---

# KPI Categories

The dashboard should use category tabs.

## Profitability

| KPI            | Formula                                   |
| -------------- | ----------------------------------------- |
| Revenue        | Reported revenue                          |
| Revenue Growth | `(Revenue_t - Revenue_t-1) / Revenue_t-1` |
| Gross Margin   | `Gross Profit / Revenue`                  |
| EBITDA         | Reported EBITDA                           |
| EBITDA Margin  | `EBITDA / Revenue`                        |
| EBIT           | Reported EBIT                             |
| Net Income     | Reported net income                       |

## Leverage

| KPI               | Formula                              |
| ----------------- | ------------------------------------ |
| Total Debt        | Short-term debt + long-term debt     |
| Net Debt          | Total Debt - Cash                    |
| Debt / EBITDA     | `Total Debt / EBITDA`                |
| Net Debt / EBITDA | `Net Debt / EBITDA`                  |
| Debt / Capital    | `Total Debt / (Total Debt + Equity)` |

## Coverage

| KPI                  | Formula                                  |
| -------------------- | ---------------------------------------- |
| EBITDA / Interest    | `EBITDA / Interest Expense`              |
| EBIT / Interest      | `EBIT / Interest Expense`                |
| Cash Flow / Interest | `Operating Cash Flow / Interest Expense` |

## Liquidity

| KPI                    | Formula                                                               |
| ---------------------- | --------------------------------------------------------------------- |
| Cash                   | Reported cash and equivalents                                         |
| Current Ratio          | `Current Assets / Current Liabilities`                                |
| Quick Ratio            | `(Cash + Short-term Investments + Receivables) / Current Liabilities` |
| Working Capital        | `Current Assets - Current Liabilities`                                |
| Short-term Debt / Cash | `Short-term Debt / Cash`                                              |

## Cash Flow

| KPI                 | Formula                       |
| ------------------- | ----------------------------- |
| Operating Cash Flow | Reported operating cash flow  |
| Capex               | Capital expenditure           |
| Free Cash Flow      | `Operating Cash Flow - Capex` |
| FCF / Debt          | `Free Cash Flow / Total Debt` |

## Balance Sheet

| KPI                 | Formula                                |
| ------------------- | -------------------------------------- |
| Total Assets        | Reported total assets                  |
| Equity              | Reported shareholders' equity          |
| Debt                | Total debt                             |
| Net Working Capital | `Current Assets - Current Liabilities` |

In the current state it is fair to hardcode all of these formulas in the backend
without any versioning.

---

---

# LangSmith

Use LangSmith to trace:

- extraction calls
- structured-output parsing
- Copilot calls
- retrieval
- tool calls
- prompts
- model versions
- latency
- token usage
- failed runs

The application should attach:

```text
company_id
document_id
filing_year
user_id
chat_session_id
correlation_id
```

as trace metadata.

---

# Security

Even though the demo uses fictional companies, implement production-like
controls.

Minimum:

- session management
- secrets outside source code
- audit logging

Never allow the frontend to construct arbitrary database queries.

---

# Error Handling

The system should explicitly distinguish:

```text
Missing
Ambiguous
Unverified
Verified
Corrected
Calculation unavailable
Source unavailable
```

Example:

```text
Interest Coverage
N/A

Reason:
Interest expense could not be reliably extracted
from the filing.
```

Never silently substitute zero.

---

# Evaluation

The system should be evaluated separately at each layer.

## Extraction

Did we extract the correct value?

## Provenance

Can we identify the exact source?

## Normalization

Did the fact map to the correct ontology concept?

## Calculation

Did the KPI formula produce the correct value?

## Retrieval

Did the correct filing evidence get retrieved?

## Copilot

Did the answer use the correct evidence?

## Rating

Did the suggested rating follow the documented methodology?

This decomposition makes debugging dramatically easier.

---
