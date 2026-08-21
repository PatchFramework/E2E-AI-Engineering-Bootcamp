import logging
from typing import Dict, Any
from sqlalchemy.orm import Session

from api.copilot.state import CopilotGraphState
from api.copilot.tools.retrieval_tools import (
    search_filing_chunks_hybrid, count_concept_frequency, get_page_content
)
from api.copilot.schemas.citation_schemas import CitationSource

logger = logging.getLogger(__name__)

def run_rag_agent(state: CopilotGraphState, db: Session) -> Dict[str, Any]:
    """
    Subagent executing agentic hybrid retrieval and text analytics over filing chunks.
    """
    company_id = state["company_id"]
    messages = state["messages"]
    last_user_msg = messages[-1].content if messages else ""
    q = last_user_msg.lower()

    logger.info(f"RAGAgent running for company_id={company_id}, query='{last_user_msg}'")

    rag_chunks = {}
    new_citations = []

    # Check if query asks for topic frequencies, risk terms, or word clouds
    if "topic" in q or "word" in q or "mention" in q or "cloud" in q or "terms" in q:
        default_underwriting_terms = [
            "Senior Debt", "Liquidity Facility", "EBITDA Headroom", "Covenants",
            "Interest Risk", "Capex", "Working Capital", "Refinancing", "Credit Facility"
        ]
        freq_res = count_concept_frequency(db, company_id, default_underwriting_terms)
        rag_chunks["concept_frequencies"] = freq_res
        rag_chunks["term_data"] = freq_res.get("term_frequencies", [])

    # Dynamic dense weighting decision
    dense_weight = 0.5
    if "covenant" in q or "clause" in q or "note" in q or "section" in q:
        dense_weight = 0.2  # prioritize exact keyword matching
    elif "why" in q or "explain" in q or "risk" in q or "strategy" in q:
        dense_weight = 0.8  # prioritize conceptual semantic vector search

    # Dynamic limit budget: 10 chunks for deep research, 5 for concise lookup
    retrieval_limit = 10 if ("detailed" in q or "all" in q or "covenant" in q) else 5

    search_res = search_filing_chunks_hybrid(
        db=db,
        query=last_user_msg,
        company_id=company_id,
        dense_weight=dense_weight,
        limit=retrieval_limit
    )

    rag_chunks["search_results"] = search_res.get("chunks", [])
    if search_res.get("citations"):
        new_citations.extend([CitationSource(**c) for c in search_res["citations"]])

    return {
        "rag_chunks": rag_chunks,
        "retrieved_sources": new_citations,
        "reasoning_status": f"Retrieved {len(search_res.get('chunks', []))} grounded filing evidence chunks"
    }
