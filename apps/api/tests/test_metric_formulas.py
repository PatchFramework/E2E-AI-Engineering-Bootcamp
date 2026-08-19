"""
test_metric_formulas.py — Unit tests for all pure KPI formula functions in metric_registry.py.

Covers:
  - Profitability: revenue_growth, gross_margin, ebitda_margin
  - Leverage: total_debt, net_debt, debt_to_ebitda, net_debt_to_ebitda, debt_to_capital
  - Coverage: ebitda_to_interest, ebit_to_interest, cash_flow_to_interest
  - Liquidity: current_ratio, quick_ratio, working_capital, short_term_debt_to_cash
  - Cash Flow: free_cash_flow, fcf_to_debt
  - Edge cases: Division by zero, negative values, missing/None inputs
"""
import math
import pytest
from api.core.metric_registry import (
    calculate_revenue_growth,
    calculate_gross_margin,
    calculate_ebitda_margin,
    calculate_total_debt,
    calculate_net_debt,
    calculate_debt_to_ebitda,
    calculate_net_debt_to_ebitda,
    calculate_debt_to_capital,
    calculate_ebitda_to_interest,
    calculate_ebit_to_interest,
    calculate_cash_flow_to_interest,
    calculate_current_ratio,
    calculate_quick_ratio,
    calculate_working_capital,
    calculate_short_term_debt_to_cash,
    calculate_free_cash_flow,
    calculate_fcf_to_debt,
    METRIC_REGISTRY
)


# ---------------------------------------------------------------------------
# Profitability Formulas
# ---------------------------------------------------------------------------

class TestProfitabilityFormulas:
    def test_revenue_growth_normal(self):
        # 1.2M vs 1.0M -> +20% (0.2)
        assert calculate_revenue_growth(1200000.0, 1000000.0) == pytest.approx(0.2)

    def test_revenue_growth_negative(self):
        # 800k vs 1.0M -> -20% (-0.2)
        assert calculate_revenue_growth(800000.0, 1000000.0) == pytest.approx(-0.2)

    def test_revenue_growth_prior_zero_or_none(self):
        assert math.isnan(calculate_revenue_growth(1000000.0, 0.0))
        assert math.isnan(calculate_revenue_growth(1000000.0, None))
        assert math.isnan(calculate_revenue_growth(None, 1000000.0))

    def test_gross_margin_normal(self):
        # GP 400k, Rev 1.0M -> 40% (0.4)
        assert calculate_gross_margin(400000.0, 1000000.0) == pytest.approx(0.4)

    def test_gross_margin_zero_rev(self):
        assert math.isnan(calculate_gross_margin(400000.0, 0.0))
        assert math.isnan(calculate_gross_margin(None, 1000000.0))

    def test_ebitda_margin_normal(self):
        # EBITDA 250k, Rev 1.0M -> 25% (0.25)
        assert calculate_ebitda_margin(250000.0, 1000000.0) == pytest.approx(0.25)

    def test_ebitda_margin_zero_rev(self):
        assert math.isnan(calculate_ebitda_margin(250000.0, 0.0))


# ---------------------------------------------------------------------------
# Leverage Formulas
# ---------------------------------------------------------------------------

class TestLeverageFormulas:
    def test_total_debt_combination(self):
        # Short-term 100k + Long-term 400k = 500k
        assert calculate_total_debt(100000.0, 400000.0) == 500000.0
        # When reported_total_debt is provided explicitly
        assert calculate_total_debt(100000.0, 400000.0, reported_total_debt=550000.0) == 550000.0
        # When only one component is present
        assert calculate_total_debt(100000.0, None) == 100000.0
        assert calculate_total_debt(None, 400000.0) == 400000.0
        assert math.isnan(calculate_total_debt(None, None))

    def test_net_debt_normal(self):
        # Total debt 500k, Cash 100k -> 400k
        assert calculate_net_debt(500000.0, 100000.0) == 400000.0
        assert math.isnan(calculate_net_debt(None, 100000.0))

    def test_debt_to_ebitda(self):
        # Total debt 500k, EBITDA 250k -> 2.0x
        assert calculate_debt_to_ebitda(500000.0, 250000.0) == pytest.approx(2.0)
        assert math.isnan(calculate_debt_to_ebitda(500000.0, 0.0))

    def test_net_debt_to_ebitda(self):
        # Net debt 400k, EBITDA 250k -> 1.6x
        assert calculate_net_debt_to_ebitda(400000.0, 250000.0) == pytest.approx(1.6)
        assert math.isnan(calculate_net_debt_to_ebitda(400000.0, 0.0))

    def test_debt_to_capital(self):
        # Debt 500k, Equity 500k -> Capital 1.0M -> 50% (0.5)
        assert calculate_debt_to_capital(500000.0, 500000.0) == pytest.approx(0.5)
        assert math.isnan(calculate_debt_to_capital(500000.0, -500000.0))  # Total capital 0


# ---------------------------------------------------------------------------
# Coverage Formulas
# ---------------------------------------------------------------------------

class TestCoverageFormulas:
    def test_ebitda_to_interest(self):
        # EBITDA 250k, Interest 50k -> 5.0x
        assert calculate_ebitda_to_interest(250000.0, 50000.0) == pytest.approx(5.0)
        assert math.isnan(calculate_ebitda_to_interest(250000.0, 0.0))

    def test_ebit_to_interest(self):
        # EBIT 150k, Interest 50k -> 3.0x
        assert calculate_ebit_to_interest(150000.0, 50000.0) == pytest.approx(3.0)
        assert math.isnan(calculate_ebit_to_interest(150000.0, 0.0))

    def test_cash_flow_to_interest(self):
        # Operating Cash Flow 200k, Interest 50k -> 4.0x
        assert calculate_cash_flow_to_interest(200000.0, 50000.0) == pytest.approx(4.0)
        assert math.isnan(calculate_cash_flow_to_interest(200000.0, 0.0))


# ---------------------------------------------------------------------------
# Liquidity Formulas
# ---------------------------------------------------------------------------

class TestLiquidityFormulas:
    def test_current_ratio(self):
        # Current Assets 600k, Current Liab 300k -> 2.0x
        assert calculate_current_ratio(600000.0, 300000.0) == pytest.approx(2.0)
        assert math.isnan(calculate_current_ratio(600000.0, 0.0))

    def test_quick_ratio(self):
        # Cash 100k + ST Inv 50k + Rec 150k = 300k. Cur Liab 200k -> 1.5x
        assert calculate_quick_ratio(100000.0, 50000.0, 150000.0, 200000.0) == pytest.approx(1.5)
        # Without ST Inv
        assert calculate_quick_ratio(100000.0, None, 100000.0, 200000.0) == pytest.approx(1.0)
        assert math.isnan(calculate_quick_ratio(None, None, None, 200000.0))
        assert math.isnan(calculate_quick_ratio(100000.0, 50000.0, 150000.0, 0.0))

    def test_working_capital(self):
        # Current Assets 600k, Current Liab 300k -> 300k
        assert calculate_working_capital(600000.0, 300000.0) == 300000.0

    def test_short_term_debt_to_cash(self):
        # Short-term Debt 50k, Cash 100k -> 0.5x
        assert calculate_short_term_debt_to_cash(50000.0, 100000.0) == pytest.approx(0.5)
        assert math.isnan(calculate_short_term_debt_to_cash(50000.0, 0.0))


# ---------------------------------------------------------------------------
# Cash Flow Formulas
# ---------------------------------------------------------------------------

class TestCashFlowFormulas:
    def test_free_cash_flow(self):
        # OCF 300k, Capex 100k -> 200k
        assert calculate_free_cash_flow(300000.0, 100000.0) == 200000.0
        assert math.isnan(calculate_free_cash_flow(None, 100000.0))

    def test_fcf_to_debt(self):
        # FCF 200k, Total Debt 500k -> 40% (0.4)
        assert calculate_fcf_to_debt(200000.0, 500000.0) == pytest.approx(0.4)
        assert math.isnan(calculate_fcf_to_debt(200000.0, 0.0))


# ---------------------------------------------------------------------------
# Registry Integrity
# ---------------------------------------------------------------------------

class TestRegistryCompleteness:
    def test_all_six_kpi_categories_present(self):
        categories = {m.category for m in METRIC_REGISTRY.values()}
        expected = {"Profitability", "Leverage", "Coverage", "Liquidity", "Cash Flow", "Balance Sheet"}
        assert expected.issubset(categories)

    def test_registry_contains_all_prd_kpis(self):
        expected_keys = {
            "revenue", "revenue_growth", "gross_margin", "ebitda", "ebitda_margin", "ebit", "net_income",
            "total_debt", "net_debt", "debt_to_ebitda", "net_debt_to_ebitda", "debt_to_capital",
            "ebitda_to_interest", "interest_coverage", "ebit_to_interest", "cash_flow_to_interest",
            "cash", "current_ratio", "quick_ratio", "working_capital", "short_term_debt_to_cash",
            "operating_cash_flow", "capex", "free_cash_flow", "fcf_to_debt",
            "total_assets", "equity", "debt", "net_working_capital"
        }
        for key in expected_keys:
            assert key in METRIC_REGISTRY, f"Missing KPI metric '{key}' in METRIC_REGISTRY"
            assert METRIC_REGISTRY[key].compute_fn is not None
