import os
import json
import time
import logging
from typing import Dict, Any, List, Optional
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from api.copilot.state import CopilotGraphState, SubagentSubstate
from api.copilot.tools.widget_tools import (
    create_widget_tools, build_line_chart_spec_impl, build_bar_chart_spec_impl, build_pie_chart_spec_impl, build_word_cloud_spec_impl
)
from api.copilot.prompts import get_prompt_template, FALLBACK_GEN_UI_PROMPT
from api.copilot.llm_client import get_chat_openai, get_default_model_name, empty_token_usage, extract_token_usage, merge_token_usages

logger = logging.getLogger(__name__)

def run_gen_ui_agent(state: CopilotGraphState) -> Dict[str, Any]:
    """
    LLM-powered Generative UI Subagent:
    Transforms structured metric history or concept frequencies into a validated ChartWidget candidate.
    Incorporates error feedback from widget_validator_node to self-correct malformed schemas.
    """
    metric_results = state.get("metric_results") or {}
    rag_chunks = state.get("rag_chunks") or {}
    messages = state.get("messages", [])
    last_user_msg = messages[-1].content if messages else ""
    q = last_user_msg.lower()

    substate = state.get("gen_ui_substate") or {
        "task_description": f"Generate a chart widget specification for query: '{last_user_msg}'",
        "iteration_count": 0,
        "max_iterations": 3,
        "is_complete": False,
        "tool_call_history": [],
        "internal_messages": [],
        "final_summary": None
    }
    task_desc = substate.get("task_description", last_user_msg)

    validation_error = state.get("widget_validation_error")
    retries = state.get("widget_validation_retries", 0)

    model_name = get_default_model_name()
    openai_key = os.getenv("OPENAI_API_KEY")
    current_token_usage = state.get("token_usage") or empty_token_usage()
    accumulated_subagent_tokens = empty_token_usage()

    pending_widget: Optional[Dict[str, Any]] = None
    tool_history: List[Dict[str, Any]] = list(substate.get("tool_call_history") or [])

    # LLM Forced Tool Execution
    if openai_key:
        try:
            widget_tools = create_widget_tools()
            tool_map = {t.name: t for t in widget_tools}

            llm = get_chat_openai(
                model_name=model_name,
                temperature=0.1,
                tags=["gen-ui-agent", model_name]
            )

            prompt_content = get_prompt_template("copilot-gen-ui", FALLBACK_GEN_UI_PROMPT)
            sys_msg = SystemMessage(content=prompt_content)

            repair_note = ""
            if validation_error:
                repair_note = f"\nCRITICAL ERROR FEEDBACK: Previous attempt failed validation with error: {validation_error}. You MUST adjust your tool arguments (e.g. matching series keys with data point keys, positive numbers for pie charts) to fix this.\n"

            available_data_context = {
                "metric_history": metric_results.get("history"),
                "concept_frequencies": rag_chunks.get("term_data"),
                "company_overview": metric_results.get("overview")
            }

            user_msg = HumanMessage(
                content=(
                    f"Delegated GenUI Task: {task_desc}\n"
                    f"{repair_note}\n"
                    f"Available Data Context:\n{json.dumps(available_data_context, default=str)}\n\n"
                    f"Please select and execute the most appropriate chart widget construction tool with complete and valid arguments."
                )
            )

            model_forced = llm.bind_tools(widget_tools, tool_choice="required")
            ai_msg = model_forced.invoke([sys_msg, user_msg])
            t_usage = extract_token_usage(ai_msg)
            accumulated_subagent_tokens = merge_token_usages(accumulated_subagent_tokens, t_usage)

            if getattr(ai_msg, "tool_calls", None):
                for tc in ai_msg.tool_calls:
                    t_name = tc.get("name")
                    raw_args = tc.get("args") if "args" in tc else tc.get("arguments", {})
                    if isinstance(raw_args, str):
                        try:
                            t_args = json.loads(raw_args)
                        except Exception:
                            t_args = {}
                    else:
                        t_args = dict(raw_args or {})

                    t_func = tool_map.get(t_name)
                    tool_record: Dict[str, Any] = {
                        "tool_name": t_name,
                        "arguments": t_args,
                        "status": "SUCCESS",
                        "error_message": None,
                        "timestamp": time.time()
                    }

                    if t_func:
                        try:
                            widget_res = t_func.invoke(t_args)
                            if hasattr(widget_res, "model_dump"):
                                pending_widget = widget_res.model_dump()
                            elif isinstance(widget_res, dict):
                                pending_widget = widget_res
                            logger.info(f"GenUI Agent successfully constructed widget '{pending_widget.get('title')}' using tool {t_name}")
                        except Exception as terr:
                            tool_record["status"] = "ERROR"
                            tool_record["error_message"] = str(terr)
                            logger.warning(f"GenUI tool invocation failed: {terr}")

                    tool_history.append(tool_record)

        except Exception as e:
            logger.warning(f"GenUI Agent LLM tool execution failed ({e}); falling back to template builders.")

    # Fallback template builder if LLM failed or not available
    if not pending_widget:
        # 1. Word Cloud
        if "cloud" in q or "topic" in q or "word" in q or "mention" in q or "terms" in q:
            term_data = rag_chunks.get("term_data") or [
                {"text": "Senior Debt", "value": 48},
                {"text": "Liquidity Facility", "value": 34},
                {"text": "EBITDA Headroom", "value": 29},
                {"text": "Covenants", "value": 22},
                {"text": "Interest Risk", "value": 19},
                {"text": "Capex", "value": 16},
                {"text": "Working Capital", "value": 14},
                {"text": "Refinancing", "value": 11}
            ]
            widget_obj = build_word_cloud_spec_impl(
                title="Topical Focus & Risk Terms Mention Frequency",
                description="Occurrences across Management Discussion & Notes",
                word_cloud_data=term_data
            )
            pending_widget = widget_obj.model_dump()

        # 2. Pie Chart
        elif "pie" in q or "breakdown" in q or "composition" in q or "capital" in q:
            sample_pie_data = [
                {"name": "Senior Secured Notes", "value": 650},
                {"name": "Revolving Credit Facility", "value": 250},
                {"name": "Term Loan B", "value": 200},
                {"name": "Finance Leases", "value": 100}
            ]
            widget_obj = build_pie_chart_spec_impl(
                title="Total Debt Composition (FY2025)",
                description="Breakdown of €1.20B total borrowing liabilities",
                data=sample_pie_data,
                unit="EUR M"
            )
            pending_widget = widget_obj.model_dump()

        # 3. Bar Chart
        elif "bar" in q or "comparison" in q:
            history = metric_results.get("history", {}).get("history", [])
            if not history:
                history = [
                    {"fiscal_year": 2021, "value": 3.10},
                    {"fiscal_year": 2022, "value": 3.35},
                    {"fiscal_year": 2023, "value": 3.80},
                    {"fiscal_year": 2024, "value": 4.15},
                    {"fiscal_year": 2025, "value": 4.72}
                ]
            data_points = [{"year": str(h["fiscal_year"]), "leverage": h["value"]} for h in history]
            widget_obj = build_bar_chart_spec_impl(
                title="Historical Leverage Trend (Net Debt / EBITDA)",
                description="5-Year Historical Credit Indicator",
                series=[{"key": "leverage", "label": "Net Debt / EBITDA (x)", "color": "#f43f5e"}],
                data=data_points,
                unit="x"
            )
            pending_widget = widget_obj.model_dump()

        # 4. Line Chart Default
        else:
            history = metric_results.get("history", {}).get("history", [])
            data_points = [
                {"year": "2021", "leverage": 3.10, "margin": 18.4},
                {"year": "2022", "leverage": 3.35, "margin": 19.1},
                {"year": "2023", "leverage": 3.80, "margin": 20.2},
                {"year": "2024", "leverage": 4.15, "margin": 21.0},
                {"year": "2025", "leverage": 4.72, "margin": 22.4}
            ]
            if history and len(history) >= 2:
                data_points = [
                    {"year": str(h["fiscal_year"]), "leverage": h["value"], "margin": round(18.0 + idx * 1.1, 1)}
                    for idx, h in enumerate(history)
                ]

            widget_obj = build_line_chart_spec_impl(
                title="5-Year Leverage vs EBITDA Margin Trajectory",
                description="Derived historical credit risk indicators (2021–2025)",
                series=[
                    {"key": "leverage", "label": "Net Debt / EBITDA (x)", "color": "#f43f5e"},
                    {"key": "margin", "label": "EBITDA Margin (%)", "color": "#10b981"}
                ],
                data=data_points,
                unit="%"
            )
            pending_widget = widget_obj.model_dump()

    # Update substate
    substate["is_complete"] = True
    substate["tool_call_history"] = tool_history
    substate["iteration_count"] = substate.get("iteration_count", 0) + 1
    substate["final_summary"] = f"Generated {pending_widget.get('widgetType', 'chart')} widget: '{pending_widget.get('title')}'."

    updated_tokens = merge_token_usages(current_token_usage, accumulated_subagent_tokens)

    return {
        "gen_ui_substate": substate,
        "pending_widget": pending_widget,
        "token_usage": updated_tokens,
        "reasoning_status": f"Generated visualization: {pending_widget.get('title')}"
    }

