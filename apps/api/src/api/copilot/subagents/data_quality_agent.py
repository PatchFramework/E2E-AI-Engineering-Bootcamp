import os
import json
import time
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage

from api.copilot.state import CopilotGraphState, SubagentSubstate, ToolCallRecord
from api.copilot.tools.audit_tools import (
    create_audit_tools, get_unverified_facts_impl, get_data_quality_issues_impl
)
from api.copilot.prompts import get_prompt_template, FALLBACK_DATA_QUALITY_PROMPT
from api.copilot.token_tracker import extract_token_usage, merge_token_usages

logger = logging.getLogger(__name__)

def run_data_quality_agent(state: CopilotGraphState, db: Session) -> Dict[str, Any]:
    """
    LLM-powered Data Quality & Accounting Audit Subagent:
    Executes audit and discrepancy inspection tools with forced initial execution.
    Summarizes findings concisely for the orchestrator and synthesizer.
    """
    company_id = state["company_id"]
    messages = state.get("messages", [])
    last_user_msg = messages[-1].content if messages else ""

    substate = state.get("audit_substate") or {
        "task_description": f"Audit accounting data quality and unverified facts for query: '{last_user_msg}'",
        "iteration_count": 0,
        "max_iterations": 3,
        "is_complete": False,
        "tool_call_history": [],
        "internal_messages": [],
        "final_summary": None
    }
    task_desc = substate.get("task_description", last_user_msg)
    tool_history: List[ToolCallRecord] = list(substate.get("tool_call_history") or [])

    model_name = os.getenv("COPILOT_LLM_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4o"
    openai_key = os.getenv("OPENAI_API_KEY")
    current_token_usage = state.get("token_usage") or {
        "prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0, "reasoning_tokens": 0, "total_tokens": 0
    }
    accumulated_subagent_tokens = {
        "prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0, "reasoning_tokens": 0, "total_tokens": 0
    }

    quality_results = dict(state.get("quality_issues") or {})
    final_summary: Optional[str] = None

    audit_tools = create_audit_tools(db)
    tool_map = {t.name: t for t in audit_tools}

    if openai_key:
        try:
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(
                model=model_name,
                temperature=0.0,
                api_key=openai_key,
                tags=["data-quality-agent", model_name],
                model_kwargs={
                    "metadata": {
                        "ls_model_name": model_name,
                        "ls_provider": "openai",
                        "company_id": company_id
                    }
                }
            )

            prompt_content = get_prompt_template("copilot-data-quality", FALLBACK_DATA_QUALITY_PROMPT)
            sys_msg = SystemMessage(content=prompt_content)
            user_msg = HumanMessage(
                content=(
                    f"Delegated Audit Task: {task_desc}\n"
                    f"Target Company ID: {company_id}\n\n"
                    f"Please execute audit tools to inspect unverified facts and active data quality issues."
                )
            )

            model_forced = llm.bind_tools(audit_tools, tool_choice="required")
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

                    if "company_id" not in t_args and t_name != "get_fact_audit_trail":
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
                                if t_name == "get_unverified_facts":
                                    quality_results["unverified_facts"] = res
                                elif t_name == "get_data_quality_issues":
                                    quality_results["active_issues"] = res
                                elif t_name == "get_fact_audit_trail":
                                    quality_results["audit_trail"] = res

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

                summary_ai = llm.invoke(internal_dialogue + [
                    HumanMessage(content="Synthesize a concise summary of the active data quality issues and unverified facts.")
                ])
                t_usage2 = extract_token_usage(summary_ai)
                accumulated_subagent_tokens = merge_token_usages(accumulated_subagent_tokens, t_usage2)
                final_summary = summary_ai.content

        except Exception as e:
            logger.warning(f"DataQualityAgent LLM tool execution failed ({e}); running deterministic fallback.")

    # Fallback execution
    if not final_summary:
        unverified = get_unverified_facts_impl(db, company_id)
        issues = get_data_quality_issues_impl(db, company_id)
        quality_results["unverified_facts"] = unverified
        quality_results["active_issues"] = issues
        final_summary = f"Audited Company #{company_id}: {issues.get('active_issues_count', 0)} issues, {unverified.get('unverified_count', 0)} unverified facts."

    # Update substate
    substate["is_complete"] = True
    substate["iteration_count"] = substate.get("iteration_count", 0) + 1
    substate["tool_call_history"] = tool_history
    substate["final_summary"] = final_summary

    updated_tokens = merge_token_usages(current_token_usage, accumulated_subagent_tokens)

    return {
        "audit_substate": substate,
        "quality_issues": quality_results,
        "token_usage": updated_tokens,
        "reasoning_status": f"Data quality audited: {final_summary[:60]}..."
    }

