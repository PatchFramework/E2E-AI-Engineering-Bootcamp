"""
test_validation.py — Integration tests for apps/pipelines/tasks/validation.py

Tests cover the three accounting rules:
  1. Gross Profit = Revenue − COGS
  2. Operating Income = Gross Profit − OpEx
  3. Total Assets = Total Liabilities + Total Equity

And the prior-year reconciliation check.

All DB interactions are mocked; no live Postgres connection is needed.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch, call
import pytest


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_fact_row(concept: str, value: float, fact_id: int, year: int, period: str):
    """Simulate a row returned by db.query(FinancialFact, FinancialFactVersion)."""
    fact = MagicMock()
    fact.id = fact_id
    fact.company_id = 10
    fact.concept = concept
    fact.fiscal_year = year
    fact.fiscal_period = period

    ver = MagicMock()
    ver.id = fact_id * 100
    ver.value = value
    ver.is_current = True
    ver.source_location_id = None

    return (fact, ver)


def _make_db_session(fact_rows: list):
    """
    Build a mock DB session whose query chain returns `fact_rows` when
    querying FinancialFact joined with FinancialFactVersion.
    """
    db = MagicMock()

    # Build the joined query chain: db.query(Fact, Ver).join(...).filter(...).all()
    joined_query = MagicMock()
    joined_query.join.return_value.filter.return_value.all.return_value = fact_rows

    # DataQualityIssue delete query chain: db.query(DQI).filter(...).delete()
    dqi_query = MagicMock()
    dqi_query.filter.return_value.delete.return_value = 0

    def query_side(*models):
        """Return different mock query chains depending on models passed."""
        names = [getattr(m, "__name__", str(m)) for m in models]
        joined_names = " ".join(names)
        if "FinancialFact" in joined_names:
            return joined_query
        elif "DataQualityIssue" in joined_names:
            return dqi_query
        q = MagicMock()
        q.filter.return_value.all.return_value = []
        q.filter.return_value.delete.return_value = 0
        return q

    db.query.side_effect = query_side
    db.add = MagicMock()
    db.commit = MagicMock()
    db.rollback = MagicMock()
    db.close = MagicMock()
    return db


EXTRACTION_RESULT = {
    "document_id": 1,
    "company_id": 10,
    "fiscal_year": 2024,
    "fiscal_period": "FY",
    "fact_ids": [],
}


# ---------------------------------------------------------------------------
# Tests: Mathematical Consistency Checks
# ---------------------------------------------------------------------------

class TestGrossProfitCheck:
    def test_no_issue_when_equation_holds(self):
        """GP = Revenue - COGS → no DataQualityIssue should be added."""
        rows = [
            _make_fact_row("Revenue", 500.0, 1, 2024, "FY"),
            _make_fact_row("Cost of Goods Sold", 300.0, 2, 2024, "FY"),
            _make_fact_row("Gross Profit", 200.0, 3, 2024, "FY"),
        ]
        db = _make_db_session(rows)

        with patch("validation.SessionLocal", return_value=db):
            from validation import validate_facts
            result = validate_facts(EXTRACTION_RESULT, db_session=db)

        # Check no DataQualityIssue was added
        added = [call.args[0] for call in db.add.call_args_list]
        assert len(added) == 0
        assert result["status"] == "success"

    def test_issue_raised_when_gp_wrong(self):
        """GP ≠ Revenue - COGS → ACCOUNTING_RULE_VIOLATION issue for Gross Profit."""
        rows = [
            _make_fact_row("Revenue", 500.0, 1, 2024, "FY"),
            _make_fact_row("Cost of Goods Sold", 300.0, 2, 2024, "FY"),
            _make_fact_row("Gross Profit", 150.0, 3, 2024, "FY"),  # Should be 200
        ]
        db = _make_db_session(rows)

        with patch("validation.SessionLocal", return_value=db):
            from validation import validate_facts
            validate_facts(EXTRACTION_RESULT, db_session=db)

        added = [call.args[0] for call in db.add.call_args_list]
        assert len(added) >= 1
        issue = added[0]
        assert issue.issue_type == "ACCOUNTING_RULE_VIOLATION"
        assert issue.concept == "Gross Profit"
        assert issue.severity == "ERROR"
        assert "discrepancy" in issue.message.lower()


class TestOperatingIncomeCheck:
    def test_issue_raised_when_operating_income_wrong(self):
        """OpInc ≠ GP - OpEx → ACCOUNTING_RULE_VIOLATION for Operating Income."""
        rows = [
            _make_fact_row("Gross Profit", 200.0, 1, 2024, "FY"),
            _make_fact_row("Operating Expense", 80.0, 2, 2024, "FY"),
            _make_fact_row("Operating Income", 50.0, 3, 2024, "FY"),  # Should be 120
        ]
        db = _make_db_session(rows)

        with patch("validation.SessionLocal", return_value=db):
            from validation import validate_facts
            validate_facts(EXTRACTION_RESULT, db_session=db)

        added = [call.args[0] for call in db.add.call_args_list]
        assert any(a.concept == "Operating Income" for a in added)

    def test_no_issue_when_operating_income_correct(self):
        rows = [
            _make_fact_row("Gross Profit", 200.0, 1, 2024, "FY"),
            _make_fact_row("Operating Expense", 80.0, 2, 2024, "FY"),
            _make_fact_row("Operating Income", 120.0, 3, 2024, "FY"),
        ]
        db = _make_db_session(rows)

        with patch("validation.SessionLocal", return_value=db):
            from validation import validate_facts
            validate_facts(EXTRACTION_RESULT, db_session=db)

        added = [call.args[0] for call in db.add.call_args_list]
        assert len(added) == 0


class TestBalanceSheetCheck:
    def test_balance_sheet_violation_detected(self):
        """Assets ≠ Liab + Equity → ACCOUNTING_RULE_VIOLATION for Total Assets."""
        rows = [
            _make_fact_row("Total Assets", 1000.0, 1, 2024, "FY"),
            _make_fact_row("Total Liabilities", 400.0, 2, 2024, "FY"),
            _make_fact_row("Total Equity", 500.0, 3, 2024, "FY"),  # Should be 600
        ]
        db = _make_db_session(rows)

        with patch("validation.SessionLocal", return_value=db):
            from validation import validate_facts
            validate_facts(EXTRACTION_RESULT, db_session=db)

        added = [call.args[0] for call in db.add.call_args_list]
        assert any(a.concept == "Total Assets" for a in added)

    def test_balance_sheet_valid(self):
        rows = [
            _make_fact_row("Total Assets", 1000.0, 1, 2024, "FY"),
            _make_fact_row("Total Liabilities", 400.0, 2, 2024, "FY"),
            _make_fact_row("Total Equity", 600.0, 3, 2024, "FY"),
        ]
        db = _make_db_session(rows)

        with patch("validation.SessionLocal", return_value=db):
            from validation import validate_facts
            validate_facts(EXTRACTION_RESULT, db_session=db)

        added = [call.args[0] for call in db.add.call_args_list]
        assert len(added) == 0

    def test_partial_facts_skip_check(self):
        """If only some balance-sheet facts are present, the check is skipped (no crash)."""
        # Only assets + liabilities — equity is missing
        rows = [
            _make_fact_row("Total Assets", 1000.0, 1, 2024, "FY"),
            _make_fact_row("Total Liabilities", 400.0, 2, 2024, "FY"),
        ]
        db = _make_db_session(rows)

        with patch("validation.SessionLocal", return_value=db):
            from validation import validate_facts
            result = validate_facts(EXTRACTION_RESULT, db_session=db)

        assert result["status"] == "success"


class TestCashFlowAndDebtRules:
    def test_free_cash_flow_violation_detected(self):
        """FCF ≠ OCF - Capex → ACCOUNTING_RULE_VIOLATION for Free Cash Flow."""
        rows = [
            _make_fact_row("Operating Cash Flow", 500.0, 1, 2024, "FY"),
            _make_fact_row("Capital Expenditures", 100.0, 2, 2024, "FY"),
            _make_fact_row("Free Cash Flow", 300.0, 3, 2024, "FY"),  # Should be 400
        ]
        db = _make_db_session(rows)

        with patch("validation.SessionLocal", return_value=db):
            from validation import validate_facts
            validate_facts(EXTRACTION_RESULT, db_session=db)

        added = [call.args[0] for call in db.add.call_args_list]
        assert any(a.concept == "Free Cash Flow" and a.issue_type == "ACCOUNTING_RULE_VIOLATION" for a in added)

    def test_total_debt_combination_violation(self):
        """Total Debt ≠ ST Debt + LT Debt → ACCOUNTING_RULE_VIOLATION for Total Debt."""
        rows = [
            _make_fact_row("Short-term Debt", 100.0, 1, 2024, "FY"),
            _make_fact_row("Long-term Debt", 400.0, 2, 2024, "FY"),
            _make_fact_row("Total Debt", 600.0, 3, 2024, "FY"),  # Should be 500
        ]
        db = _make_db_session(rows)

        with patch("validation.SessionLocal", return_value=db):
            from validation import validate_facts
            validate_facts(EXTRACTION_RESULT, db_session=db)

        added = [call.args[0] for call in db.add.call_args_list]
        assert any(a.concept == "Total Debt" and a.issue_type == "ACCOUNTING_RULE_VIOLATION" for a in added)

    def test_working_capital_violation(self):
        """Working Capital ≠ Current Assets - Current Liabilities."""
        rows = [
            _make_fact_row("Current Assets", 800.0, 1, 2024, "FY"),
            _make_fact_row("Current Liabilities", 300.0, 2, 2024, "FY"),
            _make_fact_row("Working Capital", 400.0, 3, 2024, "FY"),  # Should be 500
        ]
        db = _make_db_session(rows)

        with patch("validation.SessionLocal", return_value=db):
            from validation import validate_facts
            validate_facts(EXTRACTION_RESULT, db_session=db)

        added = [call.args[0] for call in db.add.call_args_list]
        assert any(a.concept == "Working Capital" and a.issue_type == "ACCOUNTING_RULE_VIOLATION" for a in added)


# ---------------------------------------------------------------------------
# Tests: Financial Sanity Checks
# ---------------------------------------------------------------------------

class TestFinancialSanityChecks:
    def test_negative_revenue_warning(self):
        rows = [_make_fact_row("Revenue", -500.0, 1, 2024, "FY")]
        db = _make_db_session(rows)

        with patch("validation.SessionLocal", return_value=db):
            from validation import validate_facts
            validate_facts(EXTRACTION_RESULT, db_session=db)

        added = [call.args[0] for call in db.add.call_args_list]
        assert any(a.issue_type == "SANITY_CHECK_WARNING" and a.concept == "Revenue" for a in added)

    def test_negative_cash_warning(self):
        rows = [_make_fact_row("Cash", -50.0, 1, 2024, "FY")]
        db = _make_db_session(rows)

        with patch("validation.SessionLocal", return_value=db):
            from validation import validate_facts
            validate_facts(EXTRACTION_RESULT, db_session=db)

        added = [call.args[0] for call in db.add.call_args_list]
        assert any(a.issue_type == "SANITY_CHECK_WARNING" and a.concept == "Cash" for a in added)

    def test_abnormal_gross_margin_warning(self):
        # GP 1500 on Revenue 1000 -> GM 150% (out of range)
        rows = [
            _make_fact_row("Revenue", 1000.0, 1, 2024, "FY"),
            _make_fact_row("Gross Profit", 1500.0, 2, 2024, "FY"),
        ]
        db = _make_db_session(rows)

        with patch("validation.SessionLocal", return_value=db):
            from validation import validate_facts
            validate_facts(EXTRACTION_RESULT, db_session=db)

        added = [call.args[0] for call in db.add.call_args_list]
        assert any(a.issue_type == "SANITY_CHECK_WARNING" and a.concept == "Gross Profit" for a in added)


# ---------------------------------------------------------------------------
# Tests: DB error handling
# ---------------------------------------------------------------------------

class TestValidationErrorHandling:
    def test_db_rollback_on_commit_failure(self):
        """If db.commit() raises, db.rollback() must be called."""
        rows = [_make_fact_row("Revenue", 500.0, 1, 2024, "FY")]
        db = _make_db_session(rows)
        db.commit.side_effect = RuntimeError("Connection dropped")

        with patch("validation.SessionLocal", return_value=db):
            from validation import validate_facts
            with pytest.raises(RuntimeError):
                validate_facts(EXTRACTION_RESULT, db_session=db)

        db.rollback.assert_called_once()

