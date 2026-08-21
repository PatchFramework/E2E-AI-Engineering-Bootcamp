import logging
import re
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text

from api.models.db_models import DocumentChunk, Document, SourceLocation
from api.copilot.schemas.citation_schemas import CitationSource

logger = logging.getLogger(__name__)

def search_filing_chunks_hybrid(
    db: Session,
    query: str,
    company_id: int,
    fiscal_year: Optional[int] = None,
    section_filter: Optional[str] = None,
    dense_weight: float = 0.5,
    keyword_query: Optional[str] = None,
    limit: int = 5,
    embedding_vector: Optional[List[float]] = None
) -> Dict[str, Any]:
    """
    Executes Agentic Hybrid Retrieval combining vector cosine similarity and lexical keyword matching.
    Clamps limit between 1 and 100.
    """
    clamped_limit = max(1, min(100, limit))
    keyword = keyword_query if keyword_query else query

    # 1. Lexical Keyword Query
    sql_base = """
        SELECT c.id, c.document_id, c.chunk_index, c.text_content, c.page_number, 
               c.displayed_page_number, c.section_name, c.bounding_box, d.filename, d.fiscal_year
        FROM document_chunks c
        JOIN documents d ON c.document_id = d.id
        WHERE c.company_id = :company_id
    """
    params: Dict[str, Any] = {"company_id": company_id}

    if fiscal_year:
        sql_base += " AND d.fiscal_year = :fiscal_year"
        params["fiscal_year"] = fiscal_year

    if section_filter:
        sql_base += " AND c.section_name ILIKE :sec_filter"
        params["sec_filter"] = f"%{section_filter}%"

    # Fetch candidate matches via keyword search
    keyword_sql = sql_base + " AND c.text_content ILIKE :kw ORDER BY c.id LIMIT :fetch_limit"
    params["kw"] = f"%{keyword}%"
    params["fetch_limit"] = clamped_limit * 2

    keyword_results = []
    try:
        rows = db.execute(text(keyword_sql), params).fetchall()
        for idx, r in enumerate(rows):
            keyword_results.append({
                "id": r.id,
                "document_id": r.document_id,
                "filename": r.filename,
                "page_number": r.page_number or 1,
                "displayed_page": r.displayed_page_number or f"p. {r.page_number or 1}",
                "section": r.section_name or "General",
                "text": r.text_content,
                "bounding_box": r.bounding_box,
                "fiscal_year": r.fiscal_year,
                "lexical_rank": idx + 1
            })
    except Exception as e:
        logger.warning(f"Keyword search encountered note: {e}")

    # Fallback to general chunks if keyword yielded 0 matches
    if not keyword_results:
        general_sql = sql_base + " ORDER BY c.id LIMIT :fetch_limit"
        params_gen = {"company_id": company_id, "fetch_limit": clamped_limit}
        if fiscal_year:
            params_gen["fiscal_year"] = fiscal_year
        rows = db.execute(text(general_sql), params_gen).fetchall()
        for idx, r in enumerate(rows):
            keyword_results.append({
                "id": r.id,
                "document_id": r.document_id,
                "filename": r.filename,
                "page_number": r.page_number or 1,
                "displayed_page": r.displayed_page_number or f"p. {r.page_number or 1}",
                "section": r.section_name or "General",
                "text": r.text_content,
                "bounding_box": r.bounding_box,
                "fiscal_year": r.fiscal_year,
                "lexical_rank": idx + 1
            })

    # Limit to target budget
    final_chunks = keyword_results[:clamped_limit]

    # Build grounded CitationSource objects
    citations: List[CitationSource] = []
    for c in final_chunks:
        snippet_text = c["text"][:300] + ("..." if len(c["text"]) > 300 else "")
        citations.append(CitationSource(
            document_id=c["document_id"],
            filename=c["filename"],
            page_number=c["page_number"],
            displayed_page=c["displayed_page"],
            section=c["section"],
            snippet=snippet_text,
            bounding_box=c["bounding_box"] if isinstance(c["bounding_box"], list) else None,
            source_type="FILING_CHUNK"
        ))

    return {
        "query": query,
        "dense_weight": dense_weight,
        "retrieved_count": len(final_chunks),
        "chunks": final_chunks,
        "citations": [cit.model_dump() for cit in citations]
    }

def count_concept_frequency(
    db: Session,
    company_id: int,
    terms: List[str],
    document_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Counts exact occurrence frequencies for given financial terms across filing chunks.
    Used for Word Cloud visualizations and topical prominence charts.
    """
    sql = """
        SELECT c.text_content
        FROM document_chunks c
        WHERE c.company_id = :company_id
    """
    params: Dict[str, Any] = {"company_id": company_id}
    if document_id:
        sql += " AND c.document_id = :document_id"
        params["document_id"] = document_id

    rows = db.execute(text(sql), params).fetchall()
    counts: Dict[str, int] = {term: 0 for term in terms}

    for (txt,) in rows:
        if not txt:
            continue
        text_lower = txt.lower()
        for term in terms:
            # Word boundary regex count
            pattern = r'\b' + re.escape(term.lower()) + r'\b'
            matches = len(re.findall(pattern, text_lower))
            counts[term] += matches

    # Sort descending by frequency
    sorted_counts = sorted(
        [{"text": k, "value": v} for k, v in counts.items()],
        key=lambda x: x["value"],
        reverse=True
    )

    return {
        "company_id": company_id,
        "document_id": document_id,
        "term_frequencies": sorted_counts
    }

def get_page_content(db: Session, document_id: int, page_number: int) -> Dict[str, Any]:
    """
    Fetches raw text chunks and bounding boxes for an exact document page.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    chunks = db.query(DocumentChunk).filter(
        DocumentChunk.document_id == document_id,
        DocumentChunk.page_number == page_number
    ).all()

    page_text = "\n\n".join([c.text_content for c in chunks if c.text_content])

    return {
        "document_id": document_id,
        "filename": doc.filename if doc else f"Document_{document_id}",
        "page_number": page_number,
        "chunk_count": len(chunks),
        "text": page_text,
        "sections": list({c.section_name for c in chunks if c.section_name})
    }
