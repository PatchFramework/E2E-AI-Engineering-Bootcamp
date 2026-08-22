import logging
from typing import Dict, Any, Callable
from sqlalchemy.orm import Session
from langgraph.graph import StateGraph, END

from api.copilot.state import CopilotGraphState
# agent nodes
from api.copilot.nodes.orchestrator_node import run_orchestrator_node
from api.copilot.subagents.financial_metric_agent import run_financial_metric_agent
from api.copilot.subagents.rag_agent import run_rag_agent
from api.copilot.subagents.data_quality_agent import run_data_quality_agent
from api.copilot.subagents.gen_ui_agent import run_gen_ui_agent
# post-processing nodes
from api.copilot.nodes.widget_validator_node import validate_widget_node
from api.copilot.nodes.synthesizer_node import run_synthesizer_node
# tool nodes
from api.copilot.tools.metric_tools import METRIC_TOOL_NODE
from api.copilot.tools.retrieval_tools import RETRIEVAL_TOOL_NODE
from api.copilot.tools.audit_tools import AUDIT_TOOL_NODE
from api.copilot.tools.widget_tools import WIDGET_TOOL_NODE

logger = logging.getLogger(__name__)

def build_copilot_graph(db: Session) -> Any:
    """
    Constructs and compiles the full LangGraph StateGraph for the Underwriting Copilot.
    """
    workflow = StateGraph(CopilotGraphState)

    # 1. Register Nodes
    # 1.1 Agents
    workflow.add_node("orchestrator", run_orchestrator_node)
    workflow.add_node("financial_metrics", lambda state: run_financial_metric_agent(state, db))
    workflow.add_node("agentic_rag", lambda state: run_rag_agent(state, db))
    workflow.add_node("data_quality", lambda state: run_data_quality_agent(state, db))
    workflow.add_node("gen_ui", run_gen_ui_agent)
    workflow.add_node("widget_validator", validate_widget_node)
    workflow.add_node("synthesizer", run_synthesizer_node)

    # 1.2 Tools
    workflow.add_node("metric_tools", METRIC_TOOL_NODE)
    workflow.add_node("retrieval_tools", RETRIEVAL_TOOL_NODE)
    workflow.add_node("audit_tools", AUDIT_TOOL_NODE)
    workflow.add_node("widget_tools", WIDGET_TOOL_NODE)

    # 2. Define Entry Point
    workflow.set_entry_point("orchestrator")

    # 3. Conditional Routing from Orchestrator
    def route_orchestrator(state: CopilotGraphState) -> str:
        plan = state.get("execution_plan", [])
        if "DIRECT_ANSWER" in plan:
            return "synthesizer"
        elif "METRICS" in plan:
            return "financial_metrics"
        elif "FILING_SEARCH" in plan:
            return "agentic_rag"
        elif "QUALITY_AUDIT" in plan:
            return "data_quality"
        elif "GEN_UI" in plan:
            return "gen_ui"
        return "synthesizer"

    workflow.add_conditional_edges(
        "orchestrator",
        route_orchestrator,
        {
            "synthesizer": "synthesizer",
            "financial_metrics": "financial_metrics",
            "agentic_rag": "agentic_rag",
            "data_quality": "data_quality",
            "gen_ui": "gen_ui"
        }
    )

    # 4. Routing from Financial Metrics
    workflow.add_edge("financial_metrics", "metric_tools")
    workflow.add_edge("metric_tools", "financial_metrics")

    def route_after_metrics(state: CopilotGraphState) -> str:
        plan = state.get("execution_plan", [])
        if "FILING_SEARCH" in plan and not state.get("rag_chunks"):
            return "agentic_rag"
        elif "QUALITY_AUDIT" in plan and not state.get("quality_issues"):
            return "data_quality"
        elif "GEN_UI" in plan and not state.get("pending_widget"):
            return "gen_ui"
        return "synthesizer"

    workflow.add_conditional_edges(
        "financial_metrics",
        route_after_metrics,
        {
            "agentic_rag": "agentic_rag",
            "data_quality": "data_quality",
            "gen_ui": "gen_ui",
            "synthesizer": "synthesizer"
        }
    )

    # 5. Routing from RAG
    workflow.add_edge("agentic_rag", "retrieval_tools")
    workflow.add_edge("retrieval_tools", "agentic_rag")
    
    def route_after_rag(state: CopilotGraphState) -> str:
        plan = state.get("execution_plan", [])
        if "GEN_UI" in plan and not state.get("pending_widget"):
            return "gen_ui"
        elif "QUALITY_AUDIT" in plan and not state.get("quality_issues"):
            return "data_quality"
        return "synthesizer"

    workflow.add_conditional_edges(
        "agentic_rag",
        route_after_rag,
        {
            "gen_ui": "gen_ui",
            "data_quality": "data_quality",
            "synthesizer": "synthesizer"
        }
    )

    # 6. Routing from Data Quality
    workflow.add_edge("data_quality", "audit_tools")
    workflow.add_edge("audit_tools", "data_quality")

    workflow.add_edge("data_quality", "synthesizer")

    # 7. Routing from GenUI to Validator
    workflow.add_edge("gen_ui", "widget_tools")
    workflow.add_edge("widget_tools", "gen_ui")
    
    workflow.add_edge("gen_ui", "widget_validator")

    # 8. Conditional Routing from Validator (Self-Correction Loop)
    def route_after_validator(state: CopilotGraphState) -> str:
        err = state.get("widget_validation_error")
        retries = state.get("widget_validation_retries", 0)
        if err and retries < 3:
            return "gen_ui" # retry
        return "synthesizer"

    workflow.add_conditional_edges(
        "widget_validator",
        route_after_validator,
        {
            "gen_ui": "gen_ui",
            "synthesizer": "synthesizer"
        }
    )

    # 9. Synthesizer completes execution
    workflow.add_edge("synthesizer", END)

    return workflow.compile()
