import logging
from typing import Dict, Any, List

from api.copilot.state import CopilotGraphState

logger = logging.getLogger(__name__)

def run_orchestrator_node(state: CopilotGraphState) -> Dict[str, Any]:
    """
    Orchestrator node: Analyzes the user's underwriting question and active context snapshot
    to plan the multi-step execution chain or route directly to a conversational response.
    """
    messages = state["messages"]
    last_user_msg = messages[-1].content if messages else ""
    q = last_user_msg.lower().strip()

    logger.info(f"Orchestrator analyzing query: '{last_user_msg}'")

    # Direct Answer Shortcuts (greetings, simple queries)
    greetings = ["hi", "hello", "hey", "who are you", "what can you do", "help"]
    if q in greetings or len(q.split()) <= 2 and any(g in q for g in ["hi", "hello", "hey"]):
        return {
            "execution_plan": ["DIRECT_ANSWER"],
            "current_step_index": 0,
            "reasoning_status": "Formulating direct answer..."
        }

    plan: List[str] = []

    # Check for visual / chart requirements
    needs_chart = any(w in q for w in ["chart", "plot", "trend", "visualize", "graph", "pie", "bar", "cloud", "topic"])

    # Check for document text / filings / risk factors / covenants
    needs_rag = any(w in q for w in ["filing", "10-k", "10-q", "annual report", "covenant", "clause", "footnote", "note", "why", "explain", "risk", "cloud", "topic", "mention"])

    # Check for accounting quality / audit issues
    needs_audit = any(w in q for w in ["audit", "discrepancy", "unverified", "reconciliation", "quality", "mismatch", "issue", "corrected"])

    # Check for financial metrics / calculation / ratios
    needs_metrics = any(w in q for w in ["ebitda", "debt", "leverage", "ratio", "margin", "coverage", "liquidity", "cash", "fcf", "growth", "revenue", "formula", "lineage", "metric"]) or needs_chart

    # Compose execution plan
    if needs_metrics:
        plan.append("METRICS")
    if needs_rag:
        plan.append("FILING_SEARCH")
    if needs_audit:
        plan.append("QUALITY_AUDIT")
    if needs_chart:
        plan.append("GEN_UI")

    # If no specific rule triggered, default to hybrid search + synthesis
    if not plan:
        plan = ["METRICS", "FILING_SEARCH"]

    plan.append("SYNTHESIZE")

    return {
        "execution_plan": plan,
        "current_step_index": 0,
        "reasoning_status": f"Planned execution chain: {' -> '.join(plan)}"
    }
