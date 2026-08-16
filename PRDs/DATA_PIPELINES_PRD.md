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
