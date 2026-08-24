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
from api.copilot.tools.retrieval_tools import (
    create_retrieval_tools, search_filing_chunks_hybrid_impl, count_concept_frequency_impl
)
from api.copilot.schemas.citation_schemas import CitationSource
from api.copilot.prompts import get_prompt_template, FALLBACK_RAG_PROMPT
from api.copilot.llm_client import get_chat_openai, get_default_model_name, empty_token_usage, extract_token_usage, merge_token_usages

logger = logging.getLogger(__name__)

def run_rag_agent(state: CopilotGraphState, config: Optional[RunnableConfig] = None, db: Optional[Session] = None) -> Dict[str, Any]:
    """
    LLM-powered Filing Research & Document RAG Subagent:
    Executes hybrid retrieval over filing chunks with forced initial tool execution.
    Features self-correcting query broadening if few or zero chunks are retrieved.
    """
    resolved_db = db or (config.get("configurable", {}).get("db") if config else None)
    should_close_db = False
    if resolved_db is None:
        resolved_db = SessionLocal()
        should_close_db = True

    try:
        return _run_rag_agent_impl(state, resolved_db)
    finally:
        if should_close_db and resolved_db:
            resolved_db.close()

def _run_rag_agent_impl(state: CopilotGraphState, db: Session) -> Dict[str, Any]:
    company_id = state["company_id"]
    messages = state.get("messages", [])
    last_user_msg = messages[-1].content if messages else ""
    q = last_user_msg.lower()

    substate = state.get("rag_substate") or {
        "task_description": f"Search 10-K/10-Q filing evidence for query: '{last_user_msg}'",
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

    rag_chunks = dict(state.get("rag_chunks") or {})
    new_citations: List[CitationSource] = []
    final_summary: Optional[str] = None

    retrieval_tools = create_retrieval_tools(db)
    tool_map = {t.name: t for t in retrieval_tools}

    if openai_key:
        try:
            llm = get_chat_openai(
                model_name=model_name,
                temperature=0.1,
                tags=["rag-agent", model_name],
                company_id=company_id
            )

            prompt_content = get_prompt_template("copilot-rag", FALLBACK_RAG_PROMPT)
            sys_msg = SystemMessage(content=prompt_content)

            # Build previous attempts context
            error_feedback = ""
            failed_calls = [h for h in tool_history if h.get("status") == "ERROR"]
            if failed_calls:
                error_feedback = "\nPrevious retrieval queries to refine/broaden:\n" + "\n".join(
                    [f"- Query '{h['arguments'].get('query')}' (Error: {h.get('error_message')})" for h in failed_calls]
                )

            user_msg = HumanMessage(
                content=(
                    f"Delegated RAG Subtask: {task_desc}\n"
                    f"Target Company ID: {company_id}\n"
                    f"{error_feedback}\n\n"
                    f"Please execute the hybrid retrieval or concept frequency tools to gather grounded text evidence."
                )
            )

            # Force tool execution on turn 1
            model_forced = llm.bind_tools(retrieval_tools, tool_choice="required")
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

                    if "company_id" not in t_args and t_name != "get_page_content":
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
                                if t_name == "search_filing_chunks_hybrid":
                                    chunks = res.get("chunks", [])
                                    rag_chunks["search_results"] = chunks
                                    if res.get("citations"):
                                        new_citations.extend([CitationSource(**c) for c in res["citations"]])
                                    # Check if 0 chunks returned
                                    if not chunks:
                                        tool_record["status"] = "ERROR"
                                        tool_record["error_message"] = "0 chunks found for query. Broaden search terms."
                                elif t_name == "count_concept_frequency":
                                    rag_chunks["concept_frequencies"] = res
                                    rag_chunks["term_data"] = res.get("term_frequencies", [])
                                elif t_name == "get_page_content":
                                    rag_chunks["page_content"] = res

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

                # Formulate clean synthesis of filing evidence
                summary_ai = llm.invoke(internal_dialogue + [
                    HumanMessage(content="Synthesize a concise summary of the retrieved filing evidence. Reference specific sections or notes where applicable.")
                ])
                t_usage2 = extract_token_usage(summary_ai)
                accumulated_subagent_tokens = merge_token_usages(accumulated_subagent_tokens, t_usage2)
                final_summary = summary_ai.content

        except Exception as e:
            logger.warning(f"RAGAgent LLM tool execution failed ({e}); running deterministic fallback.")

    # Fallback execution if LLM unavailable or failed
    if not final_summary:
        if "topic" in q or "word" in q or "mention" in q or "cloud" in q or "terms" in q:
            default_underwriting_terms = [
                "Senior Debt", "Liquidity Facility", "EBITDA Headroom", "Covenants",
                "Interest Risk", "Capex", "Working Capital", "Refinancing", "Credit Facility"
            ]
            freq_res = count_concept_frequency_impl(db, company_id, default_underwriting_terms)
            rag_chunks["concept_frequencies"] = freq_res
            rag_chunks["term_data"] = freq_res.get("term_frequencies", [])

        dense_weight = 0.2 if ("covenant" in q or "clause" in q or "note" in q) else 0.8
        retrieval_limit = 10 if ("detailed" in q or "all" in q or "covenant" in q) else 5

        search_res = search_filing_chunks_hybrid_impl(
            db=db,
            query=last_user_msg,
            company_id=company_id,
            dense_weight=dense_weight,
            limit=retrieval_limit
        )

        rag_chunks["search_results"] = search_res.get("chunks", [])
        if search_res.get("citations"):
            new_citations.extend([CitationSource(**c) for c in search_res["citations"]])

        final_summary = f"Retrieved {len(search_res.get('chunks', []))} filing evidence chunks for Company #{company_id}."

    # Update substate
    substate["is_complete"] = True
    substate["iteration_count"] = substate.get("iteration_count", 0) + 1
    substate["tool_call_history"] = tool_history
    substate["final_summary"] = final_summary

    updated_tokens = merge_token_usages(current_token_usage, accumulated_subagent_tokens)

    return {
        "rag_substate": substate,
        "rag_chunks": rag_chunks,
        "retrieved_sources": new_citations,
        "token_usage": updated_tokens,
        "reasoning_status": f"Filing evidence retrieved: {final_summary[:60]}..."
    }

