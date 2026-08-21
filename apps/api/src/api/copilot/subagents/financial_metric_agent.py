import logging
from typing import Dict, Any
from sqlalchemy.orm import Session
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from api.copilot.state import CopilotGraphState
from api.copilot.tools.metric_tools import (
    get_company_metrics, get_metric_history, get_fact_lineage, evaluate_formula
)
from api.copilot.schemas.citation_schemas import CitationSource

logger = logging.getLogger(__name__)

def run_financial_metric_agent(state: CopilotGraphState, db: Session) -> Dict[str, Any]:
    """
    Subagent executing deterministic calculations and metric lookups based on user query and state.
    """
    company_id = state["company_id"]
    active_metric = state.get("active_metric")
    messages = state["messages"]
    last_user_msg = messages[-1].content if messages else ""
    q = last_user_msg.lower()

    logger.info(f"FinancialMetricAgent running for company_id={company_id}, active_metric={active_metric}")

    metric_results = {}
    new_citations = []

    # 1. Check if user asked for specific history/trend or active KPI
    target_metric = None
    if active_metric and active_metric.lower() in q:
        target_metric = active_metric
    elif "leverage" in q or "debt_to_ebitda" in q or "net debt" in q:
        target_metric = "net_debt_to_ebitda"
    elif "ebitda margin" in q or "margin" in q:
        target_metric = "ebitda_margin"
    elif "interest coverage" in q or "coverage" in q:
        target_metric = "ebitda_to_interest"
    elif "current ratio" in q or "liquidity" in q:
        target_metric = "current_ratio"
    elif "fcf" in q or "free cash flow" in q:
        target_metric = "free_cash_flow"

    # 2. Fetch history if trend or multi-year requested
    if target_metric and ("trend" in q or "year" in q or "history" in q or "compare" in q or "chart" in q):
        history_res = get_metric_history(db, company_id, target_metric)
        metric_results["history"] = history_res
        
        # Also fetch lineage for latest year for grounding
        lineage_res = get_fact_lineage(db, company_id, target_metric, 2025)
        metric_results["lineage"] = lineage_res
        if lineage_res.get("citations"):
            new_citations.extend([CitationSource(**c) for c in lineage_res["citations"]])

    # 3. Always include overview metrics
    overview = get_company_metrics(db, company_id)
    metric_results["overview"] = overview

    return {
        "metric_results": metric_results,
        "retrieved_sources": new_citations,
        "reasoning_status": "Calculated deterministic credit metrics & retrieved fact lineage"
    }
