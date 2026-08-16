# Airflow Pipeline

Recommended DAG:

```text
filing_ingestion
      ↓
document_validation
      ↓
pdf_processing
      ↓
layout_extraction
      ↓
financial_fact_extraction
      ↓
ontology_normalization
      ↓
fact_validation
      ↓
reconciliation
      ↓
financial_fact_persistence
      ↓
metric_calculation
      ↓
embedding_generation
      ↓
vector_indexing
      ↓
quality_report
```

Each stage should be independently retryable.

---

# Idempotency & Processing Bypass

Every Airflow task should be idempotent.

A filing should have a content hash:

```text
sha256(pdf)
```

If the same filing is processed, the system must check if the content hash is
identical to a previously processed document.

- **Identical Hash**: If the hash is identical, the pipeline must **bypass
  processing entirely** (meaning no ingestion, parsing, or extraction tasks are
  re-executed for this file, assuming the core extraction codebase has not
  changed).
- **Different Hash**: If the hash differs, it is treated as a new or modified
  document and processed accordingly.

Example:

```text
Document
content_hash = abc123
```

If a document with hash `abc123` is uploaded again, the system immediately
recognizes it and skips reprocessing.

---

# Reprocessing

The architecture should support:

```text
Reprocess filing
```

because extraction models will change.

For example:

```text
Extraction model v1
      ↓
financial facts

Extraction model v2
      ↓
new fact versions
```

Do not destroy the original extraction.

This also allows model evaluation.

---

# Pipeline Processing Details

## 1. Auto-Metadata Extraction on Upload
Before triggering the pipeline, the upload API performs a pre-processing step:
- Extracts the content hash (SHA-256) of the document.
- Performs a fast LLM inference (e.g. `gpt-4o-mini`) on the first 3 pages to extract document metadata:
  - `company_name` (associated with existing companies, or triggers creation of a new one).
  - `fiscal_year` (strictly `YYYY`).
  - `fiscal_period` (`Q1`, `Q2`, `Q3`, `Q4`, or `FY` + 2-digit year).
  - `document_type` (`10-K`, `10-Q`, `Annual Report`).
- Bypasses triggering the Airflow pipeline if the content hash exists in the database.

## 2. Deterministic Parsing vs. LLM Fallback (OCR)
To balance efficiency and quality, pages are processed as follows:
- **Prioritize Deterministic Parsing:** PyMuPDF parses the digital layout (text characters, paragraphs, headings, tables using `find_tables`).
- **Trigger OCR Fallback:** 
  - If a page has `< 100` characters of selectable text, or is detected as image-only/scanned, or if structural tables fail to parse deterministically, the page is flagged for OCR.
  - OCR is performed by rendering the page as a PNG image and sending it to **OpenAI Vision API** (e.g. `gpt-4o-mini`) with layout-preserving extraction prompts.
- **Header/Footer Removal:** Ignore text elements in the top 5% and bottom 5% page coordinate ranges.
- **Dual Page Numbering:** Track both the physical index of the PDF file (1-based physical page number) and the displayed page label (printed numbering, e.g. Roman numerals or page offsets). Both are written to source locations and chunks to align the UI reader and text references.
- **Location-ID Tagging:** During parsing, every text block and table cell is mapped to a unique `location_id` index. The text blocks presented to the extraction model are prefixed with their ID (e.g. `[Loc: 104] Cash: 2,540 million`).
- **Multi-page tables:** Tables that touch consecutive page borders and have matching column headings are stitched together in memory before LLM fact extraction.


## 3. Fact Extraction & Mapping Schema
- The combined page layout texts/tables are sent to `gpt-4o` using the `instructor` package.
- The extraction targets all facts needed for the KPI definitions (such as `revenue`, `cost_of_goods_sold`, `gross_profit`, `operating_expense`, `operating_income`, `ebitda`, `net_income`, `total_debt`, `cash`, `current_assets`, `current_liabilities`, `equity`, `operating_cash_flow`, `capex`, `total_assets`, `total_liabilities`).
- Each fact is returned with its corresponding `location_id` (prefixed in the parsed text block), the page number (physical index), the displayed page label, and the `exact_quote` where the number was found.
- The pipeline directly links each fact to its source coordinates using the `location_id`, avoiding fragile post-hoc string searches.


## 4. Chunking Refinements & pgvector Indexing (RAG Prep)
- **Irrelevant Page Filtering:** Pages identified as Cover Pages, Table of Contents (TOC), or purely empty navigational pages containing only a section title are detected and filtered out of chunking/indexing.
- **Chunk Contextualization via Hierarchical Paths:** 
  - To prevent embedding semantic drift (e.g. confusing an outlook or strategy section with actual historical statements), every text chunk is prefixed with its layout section hierarchical path (e.g., `Section Path: FY26 Financial results > Cashflow vs target\n\n[Chunk text...]`).
  - Embeddings are generated and stored in `document_chunks` partitioned strictly by `company_id`.

## 5. In-Depth Accounting Validation
- Perform full mathematical checks:
  - `gross_profit == revenue - cost_of_goods_sold`
  - `operating_income == gross_profit - operating_expense`
  - `net_income == operating_income - interest_expense - tax_expense + other_income`
  - `total_assets == total_liabilities + equity`
- If any check fails, or if prior-year figures do not reconcile with the database records of that prior period, a `DataQualityIssue` is written to PostgreSQL for analyst review.


