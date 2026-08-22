import logging
from typing import Dict, Any, List
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

logger = logging.getLogger(__name__)

def build_copilot_graph(db: Session) -> Any:
    """
    Constructs and compiles the full LangGraph StateGraph for the Underwriting Copilot.
    Implements a centralized Hub-and-Spoke multi-agent topology:
    - Orchestrator plans, delegates targeted subtasks, and re-evaluates outputs.
    - Specialized subagents execute tools with forced initial execution.
    - GenUI validator features a self-healing retry loop.
    - Synthesizer produces final credit analysis from clean narrative history.
    """
    workflow = StateGraph(CopilotGraphState)

    # 1. Register Agent Nodes
    workflow.add_node("orchestrator", run_orchestrator_node)
    workflow.add_node("financial_metrics", lambda state: run_financial_metric_agent(state, db))
    workflow.add_node("agentic_rag", lambda state: run_rag_agent(state, db))
    workflow.add_node("data_quality", lambda state: run_data_quality_agent(state, db))
    workflow.add_node("gen_ui", run_gen_ui_agent)
    workflow.add_node("widget_validator", validate_widget_node)
    workflow.add_node("synthesizer", run_synthesizer_node)

    # 2. Define Entry Point
    workflow.set_entry_point("orchestrator")

    # 3. Dynamic Hub Routing from Orchestrator
    def route_from_orchestrator(state: CopilotGraphState) -> str:
        plan = state.get("execution_plan", [])
        completed = set(state.get("completed_steps") or [])

        if "DIRECT_ANSWER" in plan:
            return "synthesizer"

        # Find next uncompleted step in execution plan
        for step in plan:
            if step not in completed:
                if step == "METRICS":
                    return "financial_metrics"
                elif step == "FILING_SEARCH":
                    return "agentic_rag"
                elif step == "QUALITY_AUDIT":
                    return "data_quality"
                elif step == "GEN_UI":
                    return "gen_ui"

        # All planned steps are finished -> Synthesize
        return "synthesizer"

    workflow.add_conditional_edges(
        "orchestrator",
        route_from_orchestrator,
        {
            "financial_metrics": "financial_metrics",
            "agentic_rag": "agentic_rag",
            "data_quality": "data_quality",
            "gen_ui": "gen_ui",
            "synthesizer": "synthesizer"
        }
    )

    # 4. Hub-and-Spoke Returns (All subagents report back to Orchestrator)
    workflow.add_edge("financial_metrics", "orchestrator")
    workflow.add_edge("agentic_rag", "orchestrator")
    workflow.add_edge("data_quality", "orchestrator")

    # 5. GenUI -> Validator -> (Self-Correction Loop or Return to Orchestrator)
    workflow.add_edge("gen_ui", "widget_validator")

    def route_from_validator(state: CopilotGraphState) -> str:
        err = state.get("widget_validation_error")
        retries = state.get("widget_validation_retries", 0)
        if err and retries < 3:
            logger.info(f"Validator triggering GenUI self-correction retry #{retries}")
            return "gen_ui"  # self-correction retry
        return "orchestrator"  # return validated/fallback widget to orchestrator hub

    workflow.add_conditional_edges(
        "widget_validator",
        route_from_validator,
        {
            "gen_ui": "gen_ui",
            "orchestrator": "orchestrator"
        }
    )

    # 6. Synthesizer completes execution
    workflow.add_edge("synthesizer", END)

    return workflow.compile()

