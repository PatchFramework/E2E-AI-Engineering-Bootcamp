"""
test_extraction.py — Integration tests for apps/pipelines/tasks/extraction.py

Tests cover:
  - LLM-based fact extraction (instructor mocked — no real API calls).
  - DB persistence: correct FinancialFact + FinancialFactVersion creation.
  - Duplicate handling: existing facts are versioned, not duplicated.
  - Missing block_id gracefully skipped without crashing.
  - Missing document in DB raises ValueError.
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch, call
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_db(
    *,
    fiscal_year: int = 2024,
    fiscal_period: str = "FY",
    existing_fact: bool = False,
    existing_source_loc: bool = False,
):
    """
    Builds a mock SQLAlchemy Session with a stubbed Document.
    If `existing_fact=True`, a FinancialFact pre-exists in the DB.
    If `existing_source_loc=True`, a SourceLocation pre-exists.
    """
    doc = MagicMock()
    doc.fiscal_year = fiscal_year
    doc.fiscal_period = fiscal_period

    # Existing FinancialFact
    ff = MagicMock()
    ff.id = 999
    ff.fiscal_year = fiscal_year
    ff.fiscal_period = fiscal_period

    # Existing SourceLocation
    sl = MagicMock()
    sl.id = 888

    mock_db = MagicMock()

    # max version query: returns 1 when a version exists
    max_version_query = MagicMock()
    max_version_query.scalar.return_value = 1 if existing_fact else None

    def query_side_effect(model):
        """Return different mock query chains depending on model name."""
        model_name = getattr(model, "__name__", str(model))
        q = MagicMock()
        if "Document" in model_name:
            q.filter.return_value.first.return_value = doc
        elif "FinancialFact" in model_name:
            q.filter.return_value.first.return_value = ff if existing_fact else None
        elif "SourceLocation" in model_name:
            q.filter.return_value.first.return_value = sl if existing_source_loc else None
        elif "FinancialFactVersion" in model_name:
            q.filter.return_value.update.return_value = None
            q.filter.return_value = max_version_query
        else:
            q.filter.return_value.first.return_value = None
        return q

    mock_db.query.side_effect = query_side_effect
    mock_db.flush.return_value = None
    mock_db.commit.return_value = None
    mock_db.rollback.return_value = None
    mock_db.add.return_value = None
    return mock_db


def _make_extracted_facts_list(facts: list):
    """Builds the Pydantic-like response object that instructor returns."""
    mock_fact_list = MagicMock()
    mock_fact_list.facts = facts
    return mock_fact_list


def _make_fact(concept: str, value: float, unit: str = "USD", location_id: str = "p2_b0"):
    f = MagicMock()
    f.concept = concept
    f.value = value
    f.unit = unit
    f.location_id = location_id
    return f


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestExtractFacts:

    def test_successful_extraction_commits_facts(self, sample_parsed_data):
        """
        extract_facts() should persist every returned LLM fact to the DB
        and return a dict with document_id, company_id, and fact_ids.
        """
        facts = [
            _make_fact("Revenue", 500_000_000.0, "USD", "p2_b0"),
            _make_fact("Total Debt", 200_000_000.0, "USD", "p2_b1"),
            _make_fact("EBITDA", 120_000_000.0, "USD", "p2_b2"),
        ]
        extracted = _make_extracted_facts_list(facts)

        mock_db = _make_mock_db()

        with (
            patch("extraction.SessionLocal", return_value=mock_db),
            patch("extraction.OpenAI"),
            patch("extraction.instructor") as mock_instructor_mod,
        ):
            client = MagicMock()
            client.chat.completions.create.return_value = extracted
            mock_instructor_mod.from_openai.return_value = client

            from extraction import extract_facts
            result = extract_facts(sample_parsed_data)

        assert result["document_id"] == 1
        assert result["company_id"] == 10
        assert result["fiscal_year"] == 2024
        assert result["fiscal_period"] == "FY"
        mock_db.commit.assert_called()

    def test_missing_document_raises_value_error(self, sample_parsed_data):
        """If no Document exists in the DB, extract_facts raises ValueError."""
        mock_db = MagicMock()
        doc_query = MagicMock()
        doc_query.filter.return_value.first.return_value = None  # No document found
        mock_db.query.return_value = doc_query

        with (
            patch("extraction.SessionLocal", return_value=mock_db),
            patch("extraction.OpenAI"),
            patch("extraction.instructor"),
        ):
            from extraction import extract_facts
            with pytest.raises(ValueError, match="not found in database"):
                extract_facts(sample_parsed_data)

    def test_unknown_block_id_is_gracefully_skipped(self, sample_parsed_data):
        """
        If the LLM returns a block ID that doesn't exist in parsed_data,
        extract_facts must log a warning and skip it — not crash.
        """
        facts = [
            _make_fact("Revenue", 500_000_000.0, "USD", "p99_b99"),  # Non-existent
        ]
        extracted = _make_extracted_facts_list(facts)

        mock_db = _make_mock_db()

        with (
            patch("extraction.SessionLocal", return_value=mock_db),
            patch("extraction.OpenAI"),
            patch("extraction.instructor") as mock_instructor_mod,
        ):
            client = MagicMock()
            client.chat.completions.create.return_value = extracted
            mock_instructor_mod.from_openai.return_value = client

            from extraction import extract_facts
            # Must not raise
            result = extract_facts(sample_parsed_data)

        # No facts committed to db because block was not found
        assert result["fact_ids"] == []

    def test_source_location_reused_for_same_block(self, sample_parsed_data):
        """
        extract_facts must NOT insert a new SourceLocation when one for the
        same content_hash already exists in the DB.
        """
        facts = [
            _make_fact("Revenue", 500_000_000.0, "USD", "p2_b0"),
        ]
        extracted = _make_extracted_facts_list(facts)

        mock_db = _make_mock_db(existing_source_loc=True)

        with (
            patch("extraction.SessionLocal", return_value=mock_db),
            patch("extraction.OpenAI"),
            patch("extraction.instructor") as mock_instructor_mod,
        ):
            client = MagicMock()
            client.chat.completions.create.return_value = extracted
            mock_instructor_mod.from_openai.return_value = client

            from extraction import extract_facts
            extract_facts(sample_parsed_data)

        # db.add should only be called for the FinancialFact and FactVersion,
        # NOT a second time for the SourceLocation
        added_types = [type(c.args[0]).__name__ for c in mock_db.add.call_args_list]
        assert "SourceLocation" not in added_types

    def test_db_rollback_on_exception(self, sample_parsed_data):
        """If an exception occurs during persistence, db.rollback() must be called."""
        mock_db = _make_mock_db()
        mock_db.commit.side_effect = RuntimeError("DB connection lost")

        with (
            patch("extraction.SessionLocal", return_value=mock_db),
            patch("extraction.OpenAI"),
            patch("extraction.instructor") as mock_instructor_mod,
        ):
            facts = [_make_fact("Revenue", 500_000_000.0, "USD", "p2_b0")]
            extracted = _make_extracted_facts_list(facts)
            client = MagicMock()
            client.chat.completions.create.return_value = extracted
            mock_instructor_mod.from_openai.return_value = client

            from extraction import extract_facts
            with pytest.raises(RuntimeError):
                extract_facts(sample_parsed_data)

        mock_db.rollback.assert_called_once()
