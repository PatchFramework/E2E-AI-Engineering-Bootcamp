import os
import json
import time
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

from api.core.database import SessionLocal
from api.copilot.state import CopilotGraphState, SubagentSubstate, ToolCallRecord
from api.copilot.tools.metric_tools import (
    create_metric_tools, get_company_metrics_impl, get_metric_history_impl, get_fact_lineage_impl
)
from api.copilot.schemas.citation_schemas import CitationSource
from api.copilot.prompts import get_prompt_template, FALLBACK_FINANCIAL_PROMPT
from api.copilot.llm_client import get_chat_openai, get_default_model_name, empty_token_usage, extract_token_usage, merge_token_usages

logger = logging.getLogger(__name__)

def run_financial_metric_agent(state: CopilotGraphState, config: Optional[RunnableConfig] = None, db: Optional[Session] = None) -> Dict[str, Any]:
    """
    LLM-powered Financial Metric Subagent:
    Executes deterministic calculations and database lookups using tool calling with forced initial execution.
    Inspects tool error feedback, logs failed calls in isolated substate, and generates a concise grounded summary.
    """
    resolved_db = db or (config.get("configurable", {}).get("db") if config else None)
    should_close_db = False
    if resolved_db is None:
        resolved_db = SessionLocal()
        should_close_db = True

    try:
        return _run_financial_metric_agent_impl(state, resolved_db)
    finally:
        if should_close_db and resolved_db:
            resolved_db.close()

def _run_financial_metric_agent_impl(state: CopilotGraphState, db: Session) -> Dict[str, Any]:
    company_id = state["company_id"]
    active_metric = state.get("active_metric")
    messages = state.get("messages", [])
    last_user_msg = messages[-1].content if messages else ""
    q = last_user_msg.lower()
    
    substate = state.get("metric_substate") or {
        "task_description": f"Look up financial credit metrics for query: '{last_user_msg}'",
        "iteration_count": 0,
        "max_iterations": 3,
        "is_complete": False,
        "tool_call_history": [],
        "internal_messages": [],
        "final_summary": None
    }
    task_desc = substate.get("task_description", last_user_msg)
    tool_history: List[ToolCallRecord] = list(substate.get("tool_call_history") or [])
    
    model_name = get_default_model_name()
    openai_key = os.getenv("OPENAI_API_KEY")
    current_token_usage = state.get("token_usage") or empty_token_usage()
    accumulated_subagent_tokens = empty_token_usage()

    metric_results = dict(state.get("metric_results") or {})
    new_citations: List[CitationSource] = []
    final_summary: Optional[str] = None

    metric_tools = create_metric_tools(db)
    tool_map = {t.name: t for t in metric_tools}

    if openai_key:
        try:
            llm = get_chat_openai(
                model_name=model_name,
                temperature=0.0,
                tags=["financial-metrics-agent", model_name],
                company_id=company_id
            )

            prompt_content = get_prompt_template("copilot-financial-metric", FALLBACK_FINANCIAL_PROMPT)
            sys_msg = SystemMessage(content=prompt_content)

            # Build previous attempts context
            error_feedback = ""
            failed_calls = [h for h in tool_history if h.get("status") == "ERROR"]
            if failed_calls:
                error_feedback = "\nPrevious tool execution errors to avoid:\n" + "\n".join(
                    [f"- Tool '{h['tool_name']}' with args {h['arguments']}: {h.get('error_message')}" for h in failed_calls]
                )

            user_msg = HumanMessage(
                content=(
                    f"Delegated Subtask: {task_desc}\n"
                    f"Target Company ID: {company_id}\n"
                    f"Active Focus Metric: {active_metric}\n"
                    f"{error_feedback}\n\n"
                    f"Please execute the relevant metric tools to gather deterministic credit data for this task."
                )
            )

            # Bind tools with forced execution on turn 1
            model_forced = llm.bind_tools(metric_tools, tool_choice="required")
            ai_msg = model_forced.invoke([sys_msg, user_msg])
            t_usage = extract_token_usage(ai_msg)
            accumulated_subagent_tokens = merge_token_usages(accumulated_subagent_tokens, t_usage)

            internal_dialogue = [sys_msg, user_msg, ai_msg]

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

                    # Ensure company_id is present if tool expects it
                    if "company_id" not in t_args and t_name != "evaluate_formula":
                        t_args["company_id"] = company_id

                    t_func = tool_map.get(t_name)
                    tool_record: ToolCallRecord = {
                        "tool_name": t_name,
                        "arguments": t_args,
                        "status": "SUCCESS",
                        "error_message": None,
                        "timestamp": time.time()
                    }

                    if t_func:
                        try:
                            res = t_func.invoke(t_args)
                            if isinstance(res, dict) and res.get("status") == "ERROR":
                                tool_record["status"] = "ERROR"
                                tool_record["error_message"] = res.get("message")
                            else:
                                if t_name == "get_metric_history":
                                    metric_results["history"] = res
                                elif t_name == "get_company_metrics":
                                    metric_results["overview"] = res
                                elif t_name == "get_fact_lineage":
                                    metric_results["lineage"] = res
                                    if res.get("citations"):
                                        new_citations.extend([CitationSource(**c) for c in res["citations"]])
                                elif t_name == "evaluate_formula":
                                    metric_results["formula_eval"] = res

                            internal_dialogue.append(ToolMessage(
                                content=json.dumps(res),
                                tool_call_id=tc.get("id", "call_0")
                            ))
                        except Exception as terr:
                            tool_record["status"] = "ERROR"
                            tool_record["error_message"] = str(terr)
                            internal_dialogue.append(ToolMessage(
                                content=json.dumps({"status": "ERROR", "message": str(terr)}),
                                tool_call_id=tc.get("id", "call_0")
                            ))
                    tool_history.append(tool_record)

                # Final synthesis pass to formulate clean summary
                summary_ai = llm.invoke(internal_dialogue + [
                    HumanMessage(content="Synthesize a concise factual summary of the retrieved credit metrics. State exact numbers.")
                ])
                t_usage2 = extract_token_usage(summary_ai)
                accumulated_subagent_tokens = merge_token_usages(accumulated_subagent_tokens, t_usage2)
                final_summary = summary_ai.content

                if not new_citations:
                    # Auto-populate fact lineage citations for active or default metric
                    if active_metric and active_metric != "None":
                        fallback_target = active_metric
                        try:
                            fallback_lineage = get_fact_lineage_impl(db, company_id, fallback_target, None)
                            if fallback_lineage.get("citations"):
                                new_citations.extend([CitationSource(**c) for c in fallback_lineage["citations"]])
                        except Exception:
                            pass

        except Exception as e:
            logger.warning(f"FinancialMetricAgent LLM tool execution failed ({e}); running deterministic fallback.")

    # Fallback execution if LLM unavailable or failed
    if not final_summary:
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

        if target_metric:
            history_res = get_metric_history_impl(db, company_id, target_metric)
            metric_results["history"] = history_res
            lineage_res = get_fact_lineage_impl(db, company_id, target_metric, None)
            metric_results["lineage"] = lineage_res
            if lineage_res.get("citations"):
                new_citations.extend([CitationSource(**c) for c in lineage_res["citations"]])

        overview = get_company_metrics_impl(db, company_id)
        metric_results["overview"] = overview
        if not new_citations:
            try:
                fallback_lineage = get_fact_lineage_impl(db, company_id, target_metric, None)
                if fallback_lineage.get("citations"):
                    new_citations.extend([CitationSource(**c) for c in fallback_lineage["citations"]])
            except Exception:
                pass
        final_summary = f"Retrieved {len(metric_results.get('overview', {}).get('metrics', {}))} credit metrics for Company #{company_id}."

    # Update substate
    substate["is_complete"] = True
    substate["iteration_count"] = substate.get("iteration_count", 0) + 1
    substate["tool_call_history"] = tool_history
    substate["final_summary"] = final_summary

    updated_tokens = merge_token_usages(current_token_usage, accumulated_subagent_tokens)

    # Formulate informative reasoning status
    resolved_metric = None
    for th in reversed(tool_history):
        if "metric_name" in th.get("arguments", {}):
            resolved_metric = th["arguments"]["metric_name"]
            break

    if resolved_metric:
        status_msg = f"Financial metrics resolved: calculated historical trend for '{resolved_metric}'"
    elif active_metric and active_metric != "None":
        status_msg = f"Financial metrics resolved for focus metric '{active_metric}'"
    else:
        status_msg = f"Financial credit metrics resolved for Company #{company_id}"

    return {
        "metric_substate": substate,
        "metric_results": metric_results,
        "retrieved_sources": new_citations,
        "token_usage": updated_tokens,
        "reasoning_status": status_msg
    }

