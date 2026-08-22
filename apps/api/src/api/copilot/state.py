import time
from typing import Annotated, List, Dict, Any, Optional, Union
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from api.copilot.schemas.citation_schemas import CitationSource
from api.copilot.token_tracker import merge_token_usages

def update_sources(current: Optional[List[CitationSource]], new: Optional[List[CitationSource]]) -> List[CitationSource]:
    """Reducer to merge citation sources uniquely by (document_id, page_number, snippet)."""
    current_list = current or []
    new_list = new or []
    seen = {(s.document_id, s.page_number, s.snippet) for s in current_list}
    result = list(current_list)
    for src in new_list:
        key = (src.document_id, src.page_number, src.snippet)
        if key not in seen:
            seen.add(key)
            result.append(src)
    return result

class ToolCallRecord(TypedDict):
    tool_name: str
    arguments: Dict[str, Any]
    status: str  # "SUCCESS" | "ERROR"
    error_message: Optional[str]
    timestamp: float

class SubagentSubstate(TypedDict, total=False):
    task_description: str
    iteration_count: int
    max_iterations: int
    is_complete: bool
    tool_call_history: List[ToolCallRecord]
    internal_messages: List[BaseMessage]
    final_summary: Optional[str]

class CleanEvent(TypedDict, total=False):
    event_type: str  # "USER_QUERY" | "ORCHESTRATOR_PLAN" | "DELEGATED_TASK" | "SUBAGENT_ANSWER" | "PLAN_REFINED" | "GEN_UI_SPEC"
    agent: str  # "user" | "orchestrator" | "financial_metrics" | "agentic_rag" | "data_quality" | "gen_ui"
    content: str
    metadata: Optional[Dict[str, Any]]
    timestamp: float

def append_clean_events(current: Optional[List[CleanEvent]], new_events: Optional[List[CleanEvent]]) -> List[CleanEvent]:
    """Reducer to append new narrative events chronologically without mutation."""
    c = list(current or [])
    if new_events:
        c.extend(new_events)
    return c

def accumulate_tokens(current: Optional[Dict[str, int]], new: Optional[Dict[str, int]]) -> Dict[str, int]:
    """Reducer to accumulate token consumption across all multi-agent graph steps."""
    return merge_token_usages(current, new)

class CopilotGraphState(TypedDict, total=False):
    # Conversational messages with LangGraph reducer
    messages: Annotated[List[BaseMessage], add_messages]

    # Clean chronological narrative history for Orchestrator and Synthesizer
    clean_event_history: Annotated[List[CleanEvent], append_clean_events]

    # Injected immutable session context
    company_id: int
    session_id: str
    user_id: Optional[str]
    active_metric: Optional[str]
    context_snapshot: Dict[str, Any]

    # Orchestrator planning & dynamic delegation
    execution_plan: List[str]             # e.g., ["METRICS", "FILING_SEARCH", "GEN_UI", "SYNTHESIZE"] or ["DIRECT_ANSWER"]
    completed_steps: List[str]
    pending_parallel_tasks: List[str]
    current_step_index: int
    reasoning_status: Optional[str]

    # Isolated substates for subagents
    metric_substate: Optional[SubagentSubstate]
    rag_substate: Optional[SubagentSubstate]
    audit_substate: Optional[SubagentSubstate]
    gen_ui_substate: Optional[SubagentSubstate]

    # Structured artifacts
    metric_results: Optional[Dict[str, Any]]
    rag_chunks: Optional[List[Dict[str, Any]]]
    quality_issues: Optional[List[Dict[str, Any]]]

    # Generative UI widget validation state
    pending_widget: Optional[Dict[str, Any]]
    widget_validation_retries: int        # 0 to 3
    widget_validation_error: Optional[str]

    # Grounded citations registry
    retrieved_sources: Annotated[List[CitationSource], update_sources]

    # Observability & Token Usage Breakdown
    run_id: Optional[str]
    turn_count: int
    model_used: Optional[str]
    token_usage: Annotated[Dict[str, int], accumulate_tokens]
