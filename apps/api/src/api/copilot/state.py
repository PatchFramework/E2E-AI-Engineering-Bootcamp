from typing import Annotated, List, Dict, Any, Optional
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from api.copilot.schemas.citation_schemas import CitationSource

def update_sources(current: List[CitationSource], new: List[CitationSource]) -> List[CitationSource]:
    """Reducer to merge citation sources uniquely by (document_id, page_number, snippet)."""
    seen = {(s.document_id, s.page_number, s.snippet) for s in current}
    result = list(current)
    for src in new:
        key = (src.document_id, src.page_number, src.snippet)
        if key not in seen:
            seen.add(key)
            result.append(src)
    return result

class CopilotGraphState(TypedDict):
    # Conversational messages with LangGraph reducer
    messages: Annotated[List[BaseMessage], add_messages]

    # Injected immutable session context
    company_id: int
    session_id: str
    user_id: Optional[str]
    active_metric: Optional[str]
    context_snapshot: Dict[str, Any]

    # Orchestrator planning
    execution_plan: List[str]             # e.g., ["METRICS", "GEN_UI", "SYNTHESIZE"] or ["DIRECT_ANSWER"]
    current_step_index: int
    reasoning_status: Optional[str]

    # Intermediate subagent results (isolated from prompt)
    metric_results: Optional[Dict[str, Any]]
    rag_chunks: Optional[List[Dict[str, Any]]]
    quality_issues: Optional[List[Dict[str, Any]]]

    # Generative UI widget validation state
    pending_widget: Optional[Dict[str, Any]]
    widget_validation_retries: int        # 0 to 3
    widget_validation_error: Optional[str]

    # Grounded citations registry
    retrieved_sources: Annotated[List[CitationSource], update_sources]

    # Observability
    run_id: Optional[str]
    turn_count: int
