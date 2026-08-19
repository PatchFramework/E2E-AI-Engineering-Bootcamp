"""
metric_registry.py — Centralized declarative registry for derived KPI metrics and formulas.

Defines KPI definitions, required canonical financial concepts, unit types,
categories, and pure deterministic calculation functions as specified in BACKEND_PRD.md.
"""
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Any
import math
import logging

logger = logging.getLogger("api.core.metric_registry")


# ---------------------------------------------------------------------------
# 1. Pure Formula Functions
# ---------------------------------------------------------------------------

def calculate_revenue_growth(revenue_curr: float, revenue_prev: float) -> float:
    """Formula: (Revenue_t - Revenue_t-1) / Revenue_t-1"""
    if revenue_prev is None or revenue_curr is None:
        return float('nan')
    if revenue_prev == 0:
        logger.warning("Prior period revenue is 0, cannot calculate Revenue Growth")
        return float('nan')
    return (revenue_curr - revenue_prev) / revenue_prev


def calculate_gross_margin(gross_profit: float, revenue: float) -> float:
    """Formula: Gross Profit / Revenue"""
    if gross_profit is None or revenue is None:
        return float('nan')
    if revenue == 0:
        logger.warning("Revenue is 0, cannot calculate Gross Margin")
        return float('nan')
    return gross_profit / revenue


def calculate_ebitda_margin(ebitda: float, revenue: float) -> float:
    """Formula: EBITDA / Revenue"""
    if ebitda is None or revenue is None:
        return float('nan')
    if revenue == 0:
        logger.warning("Revenue is 0, cannot calculate EBITDA Margin")
        return float('nan')
    return ebitda / revenue


def calculate_total_debt(short_term_debt: Optional[float], long_term_debt: Optional[float], reported_total_debt: Optional[float] = None) -> float:
    """Formula: Short-term debt + Long-term debt (or reported total debt)"""
    if reported_total_debt is not None:
        return reported_total_debt
    if short_term_debt is not None and long_term_debt is not None:
        return short_term_debt + long_term_debt
    if short_term_debt is not None:
        return short_term_debt
    if long_term_debt is not None:
        return long_term_debt
    return float('nan')


def calculate_net_debt(total_debt: float, cash: float) -> float:
    """Formula: Total Debt - Cash"""
    if total_debt is None or cash is None:
        return float('nan')
    return total_debt - cash


def calculate_debt_to_ebitda(total_debt: float, ebitda: float) -> float:
    """Formula: Total Debt / EBITDA"""
    if total_debt is None or ebitda is None:
        return float('nan')
    if ebitda == 0:
        logger.warning("EBITDA is 0, cannot calculate Debt / EBITDA")
        return float('nan')
    return total_debt / ebitda


def calculate_net_debt_to_ebitda(net_debt: float, ebitda: float) -> float:
    """Formula: Net Debt / EBITDA"""
    if net_debt is None or ebitda is None:
        return float('nan')
    if ebitda == 0:
        logger.warning("EBITDA is 0, cannot calculate Net Debt / EBITDA")
        return float('nan')
    return net_debt / ebitda


def calculate_debt_to_capital(total_debt: float, equity: float) -> float:
    """Formula: Total Debt / (Total Debt + Equity)"""
    if total_debt is None or equity is None:
        return float('nan')
    total_capital = total_debt + equity
    if total_capital == 0:
        logger.warning("Total capital (Debt + Equity) is 0, cannot calculate Debt / Capital")
        return float('nan')
    return total_debt / total_capital


def calculate_ebitda_to_interest(ebitda: float, interest_expense: float) -> float:
    """Formula: EBITDA / Interest Expense"""
    if ebitda is None or interest_expense is None:
        return float('nan')
    if interest_expense == 0:
        logger.warning("Interest expense is 0, cannot calculate EBITDA / Interest")
        return float('nan')
    return ebitda / interest_expense


def calculate_ebit_to_interest(ebit: float, interest_expense: float) -> float:
    """Formula: EBIT / Interest Expense"""
    if ebit is None or interest_expense is None:
        return float('nan')
    if interest_expense == 0:
        logger.warning("Interest expense is 0, cannot calculate EBIT / Interest")
        return float('nan')
    return ebit / interest_expense


def calculate_cash_flow_to_interest(operating_cash_flow: float, interest_expense: float) -> float:
    """Formula: Operating Cash Flow / Interest Expense"""
    if operating_cash_flow is None or interest_expense is None:
        return float('nan')
    if interest_expense == 0:
        logger.warning("Interest expense is 0, cannot calculate Cash Flow / Interest")
        return float('nan')
    return operating_cash_flow / interest_expense


def calculate_current_ratio(current_assets: float, current_liabilities: float) -> float:
    """Formula: Current Assets / Current Liabilities"""
    if current_assets is None or current_liabilities is None:
        return float('nan')
    if current_liabilities == 0:
        logger.warning("Current liabilities is 0, cannot calculate Current Ratio")
        return float('nan')
    return current_assets / current_liabilities


def calculate_quick_ratio(
    cash: Optional[float],
    short_term_investments: Optional[float],
    receivables: Optional[float],
    current_liabilities: float
) -> float:
    """Formula: (Cash + Short-term Investments + Receivables) / Current Liabilities"""
    if current_liabilities is None or current_liabilities == 0:
        return float('nan')
    
    quick_assets = 0.0
    has_components = False
    
    if cash is not None:
        quick_assets += cash
        has_components = True
    if short_term_investments is not None:
        quick_assets += short_term_investments
        has_components = True
    if receivables is not None:
        quick_assets += receivables
        has_components = True
        
    if not has_components:
        return float('nan')
        
    return quick_assets / current_liabilities


def calculate_working_capital(current_assets: float, current_liabilities: float) -> float:
    """Formula: Current Assets - Current Liabilities"""
    if current_assets is None or current_liabilities is None:
        return float('nan')
    return current_assets - current_liabilities


def calculate_short_term_debt_to_cash(short_term_debt: float, cash: float) -> float:
    """Formula: Short-term Debt / Cash"""
    if short_term_debt is None or cash is None:
        return float('nan')
    if cash == 0:
        logger.warning("Cash is 0, cannot calculate Short-term Debt / Cash")
        return float('nan')
    return short_term_debt / cash


def calculate_free_cash_flow(operating_cash_flow: float, capex: float) -> float:
    """Formula: Operating Cash Flow - Capex"""
    if operating_cash_flow is None or capex is None:
        return float('nan')
    return operating_cash_flow - capex


def calculate_fcf_to_debt(free_cash_flow: float, total_debt: float) -> float:
    """Formula: Free Cash Flow / Total Debt"""
    if free_cash_flow is None or total_debt is None:
        return float('nan')
    if total_debt == 0:
        logger.warning("Total Debt is 0, cannot calculate FCF / Debt")
        return float('nan')
    return free_cash_flow / total_debt


# ---------------------------------------------------------------------------
# 2. Metric Definition Configuration Class
# ---------------------------------------------------------------------------

@dataclass
class MetricConfig:
    key: str
    display_name: str
    category: str
    formula_expression: str
    unit: str
    required_concepts: List[str]
    description: str
    is_multi_period: bool = False
    compute_fn: Optional[Callable] = None


# ---------------------------------------------------------------------------
# 3. Master Metric Registry
# ---------------------------------------------------------------------------

METRIC_REGISTRY: Dict[str, MetricConfig] = {
    # ------------------ PROFITABILITY ------------------
    "revenue": MetricConfig(
        key="revenue",
        display_name="Revenue",
        category="Profitability",
        formula_expression="Reported revenue",
        unit="EUR",
        required_concepts=["Revenue"],
        description="Reported top-line gross revenue for the period.",
        compute_fn=lambda facts, prior_facts: facts.get("revenue")
    ),
    "revenue_growth": MetricConfig(
        key="revenue_growth",
        display_name="Revenue Growth",
        category="Profitability",
        formula_expression="(Revenue_t - Revenue_t-1) / Revenue_t-1",
        unit="%",
        required_concepts=["Revenue"],
        description="Year-over-year percentage change in total revenue.",
        is_multi_period=True,
        compute_fn=lambda facts, prior_facts: calculate_revenue_growth(
            facts.get("revenue"),
            prior_facts.get("revenue") if prior_facts else None
        )
    ),
    "gross_margin": MetricConfig(
        key="gross_margin",
        display_name="Gross Margin",
        category="Profitability",
        formula_expression="Gross Profit / Revenue",
        unit="%",
        required_concepts=["Gross Profit", "Revenue"],
        description="Gross profit as a percentage of total revenue.",
        compute_fn=lambda facts, prior_facts: calculate_gross_margin(
            facts.get("gross_profit"), facts.get("revenue")
        )
    ),
    "ebitda": MetricConfig(
        key="ebitda",
        display_name="EBITDA",
        category="Profitability",
        formula_expression="Reported EBITDA",
        unit="EUR",
        required_concepts=["EBITDA"],
        description="Earnings before interest, taxes, depreciation, and amortization.",
        compute_fn=lambda facts, prior_facts: facts.get("ebitda")
    ),
    "ebitda_margin": MetricConfig(
        key="ebitda_margin",
        display_name="EBITDA Margin",
        category="Profitability",
        formula_expression="EBITDA / Revenue",
        unit="%",
        required_concepts=["EBITDA", "Revenue"],
        description="EBITDA as a percentage of total revenue.",
        compute_fn=lambda facts, prior_facts: calculate_ebitda_margin(
            facts.get("ebitda"), facts.get("revenue")
        )
    ),
    "ebit": MetricConfig(
        key="ebit",
        display_name="EBIT",
        category="Profitability",
        formula_expression="Reported EBIT",
        unit="EUR",
        required_concepts=["Operating Income"],
        description="Operating earnings before interest and taxes.",
        compute_fn=lambda facts, prior_facts: facts.get("operating_income") if facts.get("operating_income") is not None else facts.get("ebit")
    ),
    "net_income": MetricConfig(
        key="net_income",
        display_name="Net Income",
        category="Profitability",
        formula_expression="Reported net income",
        unit="EUR",
        required_concepts=["Net Income"],
        description="Bottom-line net profit after all expenses and taxes.",
        compute_fn=lambda facts, prior_facts: facts.get("net_income")
    ),

    # ------------------ LEVERAGE ------------------
    "total_debt": MetricConfig(
        key="total_debt",
        display_name="Total Debt",
        category="Leverage",
        formula_expression="Short-term debt + Long-term debt",
        unit="EUR",
        required_concepts=["Total Debt"],
        description="Total interest-bearing debt obligations.",
        compute_fn=lambda facts, prior_facts: (
            facts.get("total_debt") if facts.get("total_debt") is not None
            else calculate_total_debt(facts.get("short_term_debt"), facts.get("long_term_debt"))
        )
    ),
    "net_debt": MetricConfig(
        key="net_debt",
        display_name="Net Debt",
        category="Leverage",
        formula_expression="Total Debt - Cash",
        unit="EUR",
        required_concepts=["Total Debt", "Cash"],
        description="Total debt minus cash and cash equivalents.",
        compute_fn=lambda facts, prior_facts: calculate_net_debt(
            facts.get("total_debt") if facts.get("total_debt") is not None
            else calculate_total_debt(facts.get("short_term_debt"), facts.get("long_term_debt")),
            facts.get("cash")
        )
    ),
    "debt_to_ebitda": MetricConfig(
        key="debt_to_ebitda",
        display_name="Debt / EBITDA",
        category="Leverage",
        formula_expression="Total Debt / EBITDA",
        unit="x",
        required_concepts=["Total Debt", "EBITDA"],
        description="Gross leverage ratio.",
        compute_fn=lambda facts, prior_facts: calculate_debt_to_ebitda(
            facts.get("total_debt") if facts.get("total_debt") is not None
            else calculate_total_debt(facts.get("short_term_debt"), facts.get("long_term_debt")),
            facts.get("ebitda")
        )
    ),
    "net_debt_to_ebitda": MetricConfig(
        key="net_debt_to_ebitda",
        display_name="Net Debt / EBITDA",
        category="Leverage",
        formula_expression="Net Debt / EBITDA",
        unit="x",
        required_concepts=["Total Debt", "Cash", "EBITDA"],
        description="Net leverage ratio indicating debt payback ability.",
        compute_fn=lambda facts, prior_facts: calculate_net_debt_to_ebitda(
            calculate_net_debt(
                facts.get("total_debt") if facts.get("total_debt") is not None
                else calculate_total_debt(facts.get("short_term_debt"), facts.get("long_term_debt")),
                facts.get("cash")
            ),
            facts.get("ebitda")
        )
    ),
    "debt_to_capital": MetricConfig(
        key="debt_to_capital",
        display_name="Debt / Capital",
        category="Leverage",
        formula_expression="Total Debt / (Total Debt + Equity)",
        unit="%",
        required_concepts=["Total Debt", "Total Equity"],
        description="Debt proportion of total capital base.",
        compute_fn=lambda facts, prior_facts: calculate_debt_to_capital(
            facts.get("total_debt") if facts.get("total_debt") is not None
            else calculate_total_debt(facts.get("short_term_debt"), facts.get("long_term_debt")),
            facts.get("total_equity")
        )
    ),

    # ------------------ COVERAGE ------------------
    "ebitda_to_interest": MetricConfig(
        key="ebitda_to_interest",
        display_name="EBITDA / Interest",
        category="Coverage",
        formula_expression="EBITDA / Interest Expense",
        unit="x",
        required_concepts=["EBITDA", "Interest Expense"],
        description="EBITDA interest coverage ratio.",
        compute_fn=lambda facts, prior_facts: calculate_ebitda_to_interest(
            facts.get("ebitda"), facts.get("interest_expense")
        )
    ),
    "interest_coverage": MetricConfig(
        key="interest_coverage",
        display_name="Interest Coverage",
        category="Coverage",
        formula_expression="EBITDA / Interest Expense",
        unit="x",
        required_concepts=["EBITDA", "Interest Expense"],
        description="Standard interest coverage ratio (alias for EBITDA / Interest).",
        compute_fn=lambda facts, prior_facts: calculate_ebitda_to_interest(
            facts.get("ebitda"), facts.get("interest_expense")
        )
    ),
    "ebit_to_interest": MetricConfig(
        key="ebit_to_interest",
        display_name="EBIT / Interest",
        category="Coverage",
        formula_expression="EBIT / Interest Expense",
        unit="x",
        required_concepts=["Operating Income", "Interest Expense"],
        description="EBIT interest coverage ratio.",
        compute_fn=lambda facts, prior_facts: calculate_ebit_to_interest(
            facts.get("operating_income") if facts.get("operating_income") is not None else facts.get("ebit"),
            facts.get("interest_expense")
        )
    ),
    "cash_flow_to_interest": MetricConfig(
        key="cash_flow_to_interest",
        display_name="Cash Flow / Interest",
        category="Coverage",
        formula_expression="Operating Cash Flow / Interest Expense",
        unit="x",
        required_concepts=["Operating Cash Flow", "Interest Expense"],
        description="Operating cash flow interest coverage ratio.",
        compute_fn=lambda facts, prior_facts: calculate_cash_flow_to_interest(
            facts.get("operating_cash_flow"), facts.get("interest_expense")
        )
    ),

    # ------------------ LIQUIDITY ------------------
    "cash": MetricConfig(
        key="cash",
        display_name="Cash",
        category="Liquidity",
        formula_expression="Reported cash and equivalents",
        unit="EUR",
        required_concepts=["Cash"],
        description="Reported cash and cash equivalents.",
        compute_fn=lambda facts, prior_facts: facts.get("cash")
    ),
    "current_ratio": MetricConfig(
        key="current_ratio",
        display_name="Current Ratio",
        category="Liquidity",
        formula_expression="Current Assets / Current Liabilities",
        unit="ratio",
        required_concepts=["Current Assets", "Current Liabilities"],
        description="Ratio of current assets to current liabilities.",
        compute_fn=lambda facts, prior_facts: calculate_current_ratio(
            facts.get("current_assets"), facts.get("current_liabilities")
        )
    ),
    "quick_ratio": MetricConfig(
        key="quick_ratio",
        display_name="Quick Ratio",
        category="Liquidity",
        formula_expression="(Cash + Short-term Investments + Receivables) / Current Liabilities",
        unit="ratio",
        required_concepts=["Current Liabilities"],
        description="Quick ratio measuring liquid assets against current liabilities.",
        compute_fn=lambda facts, prior_facts: calculate_quick_ratio(
            facts.get("cash"),
            facts.get("short_term_investments"),
            facts.get("receivables"),
            facts.get("current_liabilities")
        )
    ),
    "working_capital": MetricConfig(
        key="working_capital",
        display_name="Working Capital",
        category="Liquidity",
        formula_expression="Current Assets - Current Liabilities",
        unit="EUR",
        required_concepts=["Current Assets", "Current Liabilities"],
        description="Net liquid operating buffer.",
        compute_fn=lambda facts, prior_facts: calculate_working_capital(
            facts.get("current_assets"), facts.get("current_liabilities")
        )
    ),
    "short_term_debt_to_cash": MetricConfig(
        key="short_term_debt_to_cash",
        display_name="Short-term Debt / Cash",
        category="Liquidity",
        formula_expression="Short-term Debt / Cash",
        unit="x",
        required_concepts=["Short-term Debt", "Cash"],
        description="Short-term debt maturity coverage by cash reserves.",
        compute_fn=lambda facts, prior_facts: calculate_short_term_debt_to_cash(
            facts.get("short_term_debt"), facts.get("cash")
        )
    ),

    # ------------------ CASH FLOW ------------------
    "operating_cash_flow": MetricConfig(
        key="operating_cash_flow",
        display_name="Operating Cash Flow",
        category="Cash Flow",
        formula_expression="Reported operating cash flow",
        unit="EUR",
        required_concepts=["Operating Cash Flow"],
        description="Cash generated from primary business operations.",
        compute_fn=lambda facts, prior_facts: facts.get("operating_cash_flow")
    ),
    "capex": MetricConfig(
        key="capex",
        display_name="Capex",
        category="Cash Flow",
        formula_expression="Capital expenditure",
        unit="EUR",
        required_concepts=["Capital Expenditures"],
        description="Capital expenditures invested in fixed assets.",
        compute_fn=lambda facts, prior_facts: facts.get("capital_expenditures") if facts.get("capital_expenditures") is not None else facts.get("capex")
    ),
    "free_cash_flow": MetricConfig(
        key="free_cash_flow",
        display_name="Free Cash Flow",
        category="Cash Flow",
        formula_expression="Operating Cash Flow - Capex",
        unit="EUR",
        required_concepts=["Operating Cash Flow", "Capital Expenditures"],
        description="Operating cash flow remaining after capital expenditures.",
        compute_fn=lambda facts, prior_facts: calculate_free_cash_flow(
            facts.get("operating_cash_flow"),
            facts.get("capital_expenditures") if facts.get("capital_expenditures") is not None else facts.get("capex")
        )
    ),
    "fcf_to_debt": MetricConfig(
        key="fcf_to_debt",
        display_name="FCF / Debt",
        category="Cash Flow",
        formula_expression="Free Cash Flow / Total Debt",
        unit="%",
        required_concepts=["Operating Cash Flow", "Capital Expenditures", "Total Debt"],
        description="Free cash flow as a proportion of total outstanding debt.",
        compute_fn=lambda facts, prior_facts: calculate_fcf_to_debt(
            calculate_free_cash_flow(
                facts.get("operating_cash_flow"),
                facts.get("capital_expenditures") if facts.get("capital_expenditures") is not None else facts.get("capex")
            ),
            facts.get("total_debt") if facts.get("total_debt") is not None
            else calculate_total_debt(facts.get("short_term_debt"), facts.get("long_term_debt"))
        )
    ),

    # ------------------ BALANCE SHEET ------------------
    "total_assets": MetricConfig(
        key="total_assets",
        display_name="Total Assets",
        category="Balance Sheet",
        formula_expression="Reported total assets",
        unit="EUR",
        required_concepts=["Total Assets"],
        description="Total reported corporate assets.",
        compute_fn=lambda facts, prior_facts: facts.get("total_assets")
    ),
    "equity": MetricConfig(
        key="equity",
        display_name="Equity",
        category="Balance Sheet",
        formula_expression="Reported shareholders' equity",
        unit="EUR",
        required_concepts=["Total Equity"],
        description="Reported shareholders' equity.",
        compute_fn=lambda facts, prior_facts: facts.get("total_equity") if facts.get("total_equity") is not None else facts.get("equity")
    ),
    "debt": MetricConfig(
        key="debt",
        display_name="Debt",
        category="Balance Sheet",
        formula_expression="Total debt",
        unit="EUR",
        required_concepts=["Total Debt"],
        description="Total reported debt obligations.",
        compute_fn=lambda facts, prior_facts: (
            facts.get("total_debt") if facts.get("total_debt") is not None
            else calculate_total_debt(facts.get("short_term_debt"), facts.get("long_term_debt"))
        )
    ),
    "net_working_capital": MetricConfig(
        key="net_working_capital",
        display_name="Net Working Capital",
        category="Balance Sheet",
        formula_expression="Current Assets - Current Liabilities",
        unit="EUR",
        required_concepts=["Current Assets", "Current Liabilities"],
        description="Short-term operational liquidity (Current Assets - Current Liabilities).",
        compute_fn=lambda facts, prior_facts: calculate_working_capital(
            facts.get("current_assets"), facts.get("current_liabilities")
        )
    ),
}
