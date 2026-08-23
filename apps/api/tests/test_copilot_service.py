import pytest
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from api.copilot.schemas.widget_schemas import (
    LineChartSpec, BarChartSpec, PieChartSpec, WordCloudSpec, TableWidgetSpec
)
from api.copilot.schemas.citation_schemas import CitationSource
from api.copilot.nodes.widget_validator_node import validate_widget_node
from api.copilot.tools.metric_tools import evaluate_formula
from api.copilot.pruning import prune_messages_state, is_turn_limit_reached
from api.copilot.nodes.orchestrator_node import run_orchestrator_node

def test_citation_source_schema():
    src = CitationSource(
        document_id=1,
        filename="FY2025_Annual_Report.pdf",
        page_number=42,
        displayed_page="p. 42",
        section="Consolidated Income Statement",
        snippet="EBITDA was €178M.",
        bounding_box=[120.0, 180.0, 480.0, 260.0]
    )
    assert src.document_id == 1
    assert src.page_number == 42
    assert src.source_type == "FILING_CHUNK"

def test_line_chart_spec_validation():
    # Valid line chart
    valid_spec = LineChartSpec(
        title="5-Year Leverage Trend",
        series=[{"key": "leverage", "label": "Net Debt / EBITDA"}],
        data=[
            {"year": "2024", "leverage": 4.1},
            {"year": "2025", "leverage": 4.7}
        ]
    )
    assert valid_spec.chartType == "line"
    assert len(valid_spec.data) == 2

    # Invalid line chart (missing series key in data)
    with pytest.raises(ValueError, match="does not contain any matching series keys"):
        LineChartSpec(
            title="Invalid",
            series=[{"key": "leverage", "label": "Net Debt / EBITDA"}],
            data=[{"year": "2024", "wrong_key": 100}]
        )

def test_pie_chart_spec_validation():
    # Valid pie chart
    valid_pie = PieChartSpec(
        title="Debt Breakdown",
        data=[
            {"name": "Term Loan", "value": 500},
            {"name": "Revolver", "value": 200}
        ]
    )
    assert valid_pie.chartType == "pie"

    # Invalid pie chart (negative value)
    with pytest.raises(ValueError, match="negative value"):
        PieChartSpec(
            title="Invalid Pie",
            data=[{"name": "Term Loan", "value": -50}]
        )

def test_word_cloud_spec_validation():
    wc = WordCloudSpec(
        title="Top Risk Factors",
        wordCloudData=[
            {"text": "Covenants", "value": 24},
            {"text": "Liquidity", "value": 18}
        ]
    )
    assert wc.widgetType == "word_cloud"
    assert len(wc.wordCloudData) == 2

def test_widget_validator_retry_and_fallback():
    # Invalid candidate
    invalid_widget = {
        "widgetType": "chart",
        "chartType": "line",
        "title": "Broken Spec",
        "series": [{"key": "leverage", "label": "Leverage"}],
        "data": [{"year": "2025", "unmatched_key": 5.0}]
    }

    state_0 = {"pending_widget": invalid_widget, "widget_validation_retries": 0}
    res_0 = validate_widget_node(state_0)
    assert res_0["widget_validation_retries"] == 1
    assert res_0["widget_validation_error"] is not None

    state_1 = {"pending_widget": invalid_widget, "widget_validation_retries": 1}
    res_1 = validate_widget_node(state_1)
    assert res_1["widget_validation_retries"] == 2

    # 3rd failure triggers fallback to TableWidgetSpec
    state_2 = {"pending_widget": invalid_widget, "widget_validation_retries": 2}
    res_2 = validate_widget_node(state_2)
    assert res_2["widget_validation_retries"] == 3
    assert res_2["pending_widget"]["widgetType"] == "table"

def test_evaluate_formula_safe_ast():
    res = evaluate_formula.invoke({"expression": "(debt - cash) / ebitda", "variables": {"debt": 1000.0, "cash": 200.0, "ebitda": 200.0}})
    assert res["status"] == "SUCCESS"
    assert res["result"] == 4.0

    div_zero = evaluate_formula.invoke({"expression": "debt / ebitda", "variables": {"debt": 500.0, "ebitda": 0.0}})
    assert div_zero["status"] == "ERROR"
    assert "Division by zero" in div_zero["message"]

def test_message_pruning_and_turn_budget():
    messages = []
    # Create 12 turns
    for i in range(12):
        messages.append(HumanMessage(content=f"User query {i}"))
        messages.append(AIMessage(content=f"Assistant response {i}"))

    pruned = prune_messages_state(messages)
    # Total messages preserved (older tool logs stripped)
    assert len(pruned) == 24
    assert is_turn_limit_reached(10) is True
    assert is_turn_limit_reached(5) is False

def test_orchestrator_planning():
    # Direct answer for greetings
    greet_state = {"messages": [HumanMessage(content="Hello!")]}
    res_greet = run_orchestrator_node(greet_state)
    assert res_greet["execution_plan"] == ["DIRECT_ANSWER"]

    # Composite query: metrics + chart
    chart_state = {"messages": [HumanMessage(content="Show me a 5-year line chart of leverage and EBITDA margin")]}
    res_chart = run_orchestrator_node(chart_state)
    assert "METRICS" in res_chart["execution_plan"]
    assert "GEN_UI" in res_chart["execution_plan"]

@pytest.mark.anyio
async def test_submit_copilot_feedback_endpoint():
    from api.routers.copilot import submit_copilot_feedback
    from api.copilot.schemas.feedback_schemas import FeedbackRequest

    req = FeedbackRequest(
        run_id="00000000-0000-0000-0000-000000000001",
        score=1,
        feedback_type="user_rating",
        comment="Great breakdown of leverage metrics"
    )
    resp = await submit_copilot_feedback(req)
    assert resp.status == "SUCCESS"
    assert resp.run_id == "00000000-0000-0000-0000-000000000001"

def test_token_tracker_extraction_and_merge():
    from api.copilot.token_tracker import extract_token_usage, merge_token_usages, format_langsmith_token_metadata

    msg = AIMessage(
        content="Credit summary",
        usage_metadata={
            "input_tokens": 150,
            "output_tokens": 80,
            "total_tokens": 230,
            "input_token_details": {"cache_read": 30},
            "output_token_details": {"reasoning": 15}
        }
    )
    extracted = extract_token_usage(msg)
    assert extracted["prompt_tokens"] == 150
    assert extracted["completion_tokens"] == 80
    assert extracted["cached_tokens"] == 30
    assert extracted["reasoning_tokens"] == 15
    assert extracted["total_tokens"] == 230

    merged = merge_token_usages(extracted, {"prompt_tokens": 50, "completion_tokens": 20, "cached_tokens": 10, "reasoning_tokens": 0, "total_tokens": 70})
    assert merged["prompt_tokens"] == 200
    assert merged["completion_tokens"] == 100
    assert merged["cached_tokens"] == 40
    assert merged["reasoning_tokens"] == 15
    assert merged["total_tokens"] == 300

    ls_meta = format_langsmith_token_metadata("gpt-4o", merged)
    assert ls_meta["ls_model_name"] == "gpt-4o"
    assert ls_meta["ls_provider"] == "openai"
    assert ls_meta["usage_metadata"]["input_tokens"] == 200
    assert ls_meta["usage_metadata"]["output_tokens"] == 100

def test_clean_event_history_reducer():
    from api.copilot.state import append_clean_events, CleanEvent

    existing: list[CleanEvent] = [
        {"event_type": "USER_QUERY", "agent": "user", "content": "Query 1", "metadata": None, "timestamp": 100.0}
    ]
    new_evs: list[CleanEvent] = [
        {"event_type": "ORCHESTRATOR_PLAN", "agent": "orchestrator", "content": "Plan A", "metadata": None, "timestamp": 101.0}
    ]
    merged = append_clean_events(existing, new_evs)
    assert len(merged) == 2
    assert merged[0]["event_type"] == "USER_QUERY"
    assert merged[1]["event_type"] == "ORCHESTRATOR_PLAN"

def test_subagent_substate_isolation():
    from api.copilot.state import SubagentSubstate

    sub: SubagentSubstate = {
        "task_description": "Retrieve EBITDA leverage",
        "iteration_count": 1,
        "max_iterations": 3,
        "is_complete": False,
        "tool_call_history": [
            {
                "tool_name": "get_metric_history",
                "arguments": {"metric_name": "leverage"},
                "status": "SUCCESS",
                "error_message": None,
                "timestamp": 123456.78
            }
        ],
        "internal_messages": [],
        "final_summary": "Retrieved 5-year leverage"
    }
    assert sub["iteration_count"] == 1
    assert len(sub["tool_call_history"]) == 1
    assert sub["tool_call_history"][0]["tool_name"] == "get_metric_history"



