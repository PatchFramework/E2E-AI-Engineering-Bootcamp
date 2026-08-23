import os
import json
import logging
from typing import Dict, Any, List
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage

from api.copilot.state import CopilotGraphState, CleanEvent
from api.copilot.pruning import is_turn_limit_reached, TURN_LIMIT_WARNING
from api.copilot.prompts import get_prompt_template, FALLBACK_SYNTHESIS_PROMPT
from api.copilot.token_tracker import extract_token_usage, merge_token_usages

logger = logging.getLogger(__name__)

def run_synthesizer_node(state: CopilotGraphState) -> Dict[str, Any]:
    """
    Synthesizer node:
    Consumes the clean chronological event narrative, validated GenUI widget, and grounded citations.
    Invokes ChatOpenAI with full LangSmith cost & token tracking to produce the final institutional credit memo.
    """
    plan = state.get("execution_plan", [])
    messages = state.get("messages", [])
    last_user_msg = messages[-1].content if messages else ""
    company_id = state.get("company_id", 1)
    context_snapshot = state.get("context_snapshot") or {}
    company_name = context_snapshot.get("companyName") or f"Company #{company_id}"
    model_name = os.getenv("COPILOT_LLM_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
    
    current_token_usage = state.get("token_usage") or {
        "prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0, "reasoning_tokens": 0, "total_tokens": 0
    }
    synthesizer_tokens = {
        "prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0, "reasoning_tokens": 0, "total_tokens": 0
    }

    clean_history: List[CleanEvent] = list(state.get("clean_event_history") or [])
    pending_widget = state.get("pending_widget")
    citations = state.get("retrieved_sources") or []

    # 1. Handle Direct Answers
    if "DIRECT_ANSWER" in plan:
        response_text = (
            f"Hello Analyst! I am your **Credit Underwriting Copilot** for **{company_name}**.\n\n"
            "I can assist you with:\n"
            "- **Deterministic KPI & Ratio Calculations**: Profitability, Leverage, Coverage, and Liquidity metrics.\n"
            "- **Historical Trend Analysis & Chart Generation**: Line, Bar, Pie charts, and Word Clouds.\n"
            "- **Filing Evidence & Footnote Grounding**: Deep-linking to exact PDF pages and bounding boxes.\n"
            "- **Accounting & Reconciliation Audits**: Detecting unverified facts and balance check discrepancies.\n\n"
            "What would you like to investigate today?"
        )
    else:
        # 2. Build Structured Narrative Context from clean_event_history
        narrative_lines: List[str] = [f"Company: {company_name} (ID: {company_id})", f"Analyst Inquiry: {last_user_msg}", ""]
        narrative_lines.append("### Chronological Workflow Execution History:")

        for ev in clean_history:
            ev_type = ev.get("event_type", "EVENT")
            agent = ev.get("agent", "agent")
            content = ev.get("content", "")
            if ev_type == "USER_QUERY":
                continue
            elif ev_type == "ORCHESTRATOR_PLAN":
                narrative_lines.append(f"- **[Orchestrator Plan]**: {content}")
            elif ev_type == "DELEGATED_TASK":
                narrative_lines.append(f"- **[Task Delegated to {agent.upper()}]**: {content}")
            elif ev_type == "SUBAGENT_ANSWER":
                narrative_lines.append(f"- **[Findings from {agent.upper()}]**: {content}")
            elif ev_type == "GEN_UI_SPEC":
                narrative_lines.append(f"- **[Generative UI Widget]**: {content}")

        # Add citations reference summary
        if citations:
            narrative_lines.append("\n### Grounded Evidence Citations:")
            for idx, cit in enumerate(citations[:8]):
                disp_page = cit.displayed_page or f"p. {cit.page_number}"
                sec = f" · {cit.section}" if cit.section else ""
                narrative_lines.append(f"- Citation [{idx}]: [{cit.filename} · {disp_page}{sec}] (markdown link: `[{cit.filename} · {disp_page}](citation:{idx})`): \"{cit.snippet[:180]}...\"")

        # Add GenUI note
        if pending_widget:
            narrative_lines.append(
                f"\nNote: A validated **{pending_widget.get('widgetType')}** widget titled **'{pending_widget.get('title')}'** has been generated and will be rendered in the UI. Reference its key visual insights."
            )

        narrative_prompt_context = "\n".join(narrative_lines)

        # 3. Invoke LLM for Final Synthesis
        openai_key = os.getenv("OPENAI_API_KEY")
        response_text = ""

        if openai_key:
            try:
                from langchain_openai import ChatOpenAI
                llm = ChatOpenAI(
                    model=model_name,
                    temperature=0.2,
                    api_key=openai_key,
                    tags=["synthesizer", model_name],
                    model_kwargs={
                        "metadata": {
                            "ls_model_name": model_name,
                            "ls_provider": "openai",
                            "company_id": company_id
                        }
                    }
                )
                system_prompt = get_prompt_template("copilot-synthesizer", FALLBACK_SYNTHESIS_PROMPT)
                ai_resp = llm.invoke([
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=narrative_prompt_context)
                ])
                if ai_resp and ai_resp.content:
                    response_text = ai_resp.content
                    synthesizer_tokens = extract_token_usage(ai_resp)
                    logger.info(f"Synthesizer completed synthesis with {model_name} (tokens: {synthesizer_tokens})")
            except Exception as e:
                logger.warning(f"Synthesizer LLM invoke failed ({e}); building deterministic summary.")


    # 4. Check Turn Limit Cap
    turn_count = state.get("turn_count", 1)
    if is_turn_limit_reached(turn_count):
        response_text += TURN_LIMIT_WARNING

    total_token_usage = merge_token_usages(current_token_usage, synthesizer_tokens)

    ai_msg = AIMessage(
        content=response_text,
        usage_metadata={
            "input_tokens": total_token_usage.get("prompt_tokens", 0),
            "output_tokens": total_token_usage.get("completion_tokens", 0),
            "total_tokens": total_token_usage.get("total_tokens", 0),
            "input_token_details": {
                "cache_read": total_token_usage.get("cached_tokens", 0)
            },
            "output_token_details": {
                "reasoning": total_token_usage.get("reasoning_tokens", 0)
            }
        },
        response_metadata={
            "model_name": model_name,
            "token_usage": total_token_usage
        }
    )

    return {
        "messages": [ai_msg],
        "token_usage": total_token_usage,
        "model_used": model_name,
        "reasoning_status": "Credit analysis synthesis complete."
    }

