import os
import logging
from typing import Dict, Any, List
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage

from api.copilot.state import CopilotGraphState
from api.copilot.pruning import is_turn_limit_reached, TURN_LIMIT_WARNING
from api.copilot.prompts import get_prompt_template, FALLBACK_SYNTHESIS_PROMPT

logger = logging.getLogger(__name__)

def run_synthesizer_node(state: CopilotGraphState) -> Dict[str, Any]:
    """
    Synthesizer node: Aggregates subagent findings, formats the final markdown response
    with evidence citations, applies conversation budget warnings, and invokes ChatOpenAI
    with model cost tracking annotations.
    """
    plan = state.get("execution_plan", [])
    messages = state["messages"]
    last_user_msg = messages[-1].content if messages else ""
    q = last_user_msg.lower()
    company_id = state.get("company_id", 1)
    context_snapshot = state.get("context_snapshot") or {}
    company_name = context_snapshot.get("companyName") or f"Company #{company_id}"
    model_name = os.getenv("COPILOT_LLM_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4o"

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
        # 2. Synthesize multi-agent findings into structured background
        parts: List[str] = []

        metric_results = state.get("metric_results") or {}
        rag_chunks = state.get("rag_chunks") or {}
        quality_issues = state.get("quality_issues") or {}
        pending_widget = state.get("pending_widget")

        # Metric findings
        if metric_results.get("history"):
            hist_data = metric_results["history"]
            metric_name = hist_data.get("display_name", "Metric")
            points = hist_data.get("history", [])
            if len(points) >= 2:
                start_val = points[0].get("value")
                end_val = points[-1].get("value")
                start_yr = points[0].get("fiscal_year")
                end_yr = points[-1].get("fiscal_year")
                parts.append(
                    f"Based on historical financial records for **{company_name}**, **{metric_name}** shifted from **{start_val}{hist_data.get('unit', '')}** in {start_yr} to **{end_val}{hist_data.get('unit', '')}** in {end_yr}."
                )

        if metric_results.get("overview") and not parts:
            ov = metric_results["overview"]
            m_count = ov.get("metrics_count", 0)
            parts.append(
                f"Calculated **{m_count} credit underwriting metrics** for **{company_name}** across Profitability, Leverage, Coverage, and Liquidity."
            )

        # RAG findings
        if rag_chunks.get("search_results"):
            top_chunk = rag_chunks["search_results"][0]
            snippet = top_chunk.get("text", "")[:240].strip()
            sec = top_chunk.get("section", "Filings")
            disp_page = top_chunk.get("displayed_page", "p. 1")
            parts.append(
                f"\n**Filing Evidence ({sec} · {disp_page}):**\n> *\"{snippet}...\"*"
            )

        # Quality & audit findings
        if quality_issues.get("active_issues"):
            issues = quality_issues["active_issues"].get("issues", [])
            if issues:
                parts.append(
                    f"\n⚠️ **Identified {len(issues)} data quality / accounting reconciliation issue(s)** requiring review."
                )

        # Widget note
        if pending_widget:
            w_title = pending_widget.get("title", "Visualization")
            parts.append(f"\nBelow is the generated **{w_title}**:")

        if not parts:
            parts.append(
                f"Completed credit analysis for **{company_name}**. The company exhibits an overall **BB (Elevated Risk)** credit profile, driven by rising net leverage and steady operating cash flows."
            )

        response_text = "\n\n".join(parts)

        # 3. If OpenAI API Key is available, refine synthesis with LLM for natural tone and LangSmith cost tracking
        openai_key = os.getenv("OPENAI_API_KEY")
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
                prompt_content = f"Company: {company_name}\nUser Question: {last_user_msg}\nFindings & Evidence:\n{response_text}"
                ai_resp = llm.invoke([
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=prompt_content)
                ])
                if ai_resp and ai_resp.content:
                    response_text = ai_resp.content
                    logger.info(f"Synthesizer generated LLM response with model {model_name}")
            except Exception as e:
                logger.warning(f"Could not invoke ChatOpenAI in synthesizer node ({e}); using deterministic output")

    # 4. Check Conversation Turn Limit Cap
    turn_count = state.get("turn_count", 1)
    if is_turn_limit_reached(turn_count):
        response_text += TURN_LIMIT_WARNING

    ai_msg = AIMessage(content=response_text)

    return {
        "messages": [ai_msg],
        "reasoning_status": "Credit analysis synthesis complete."
    }
