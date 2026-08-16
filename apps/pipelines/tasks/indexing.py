import logging
import json
from typing import Dict, Any, List
from openai import OpenAI

from api.core.config import config
from api.core.database import SessionLocal
from api.models.db_models import Document, DocumentChunk

logger = logging.getLogger("pipelines.tasks.indexing")

def is_irrelevant_page(page_text: str) -> bool:
    """
    Checks if a page's text indicates it is a Cover Page, TOC, or empty page.
    """
    text_lower = page_text.lower().strip()
    if not text_lower:
        return True
    
    # Table of Contents patterns
    if "table of contents" in text_lower or "index to" in text_lower or "index of" in text_lower:
        return True
        
    # Cover pages (long headers/logos, short text)
    if len(text_lower) < 200 and ("annual report" in text_lower or "form 10-k" in text_lower or "form 10-q" in text_lower):
        return True
        
    return False


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 150) -> List[str]:
    """
    Splits text into overlapping segments.
    """
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


def index_document_chunks(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Filters out Cover/TOC pages, segments page text into chunks, generates embeddings,
    and saves them in PostgreSQL `document_chunks` table.
    """
    document_id = parsed_data["document_id"]
    company_id = parsed_data["company_id"]
    
    logger.info(f"Starting chunk indexing for document_id {document_id}")
    
    db = SessionLocal()
    try:
        # Fetch document metadata
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise ValueError(f"Document with ID {document_id} not found in database.")
            
        fiscal_year = doc.fiscal_year
        fiscal_period = doc.fiscal_period
        
        # Clear out any existing chunks for this document
        db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).delete()
        db.commit()
        
        openai_client = OpenAI(api_key=config.OPENAI_API_KEY)
        saved_chunks_count = 0
        
        for page in parsed_data["pages"]:
            page_num = page["page_number"]
            displayed_page_number = page["displayed_page_number"]
            section_path = page["section_path"]
            
            # Combine block texts on this page
            page_text = " ".join([b["text"] for b in page["blocks"]])
            
            # Filter Table of Contents and Cover pages
            if is_irrelevant_page(page_text):
                logger.info(f"Page {page_num} flagged as irrelevant (Cover/TOC). Skipping indexing.")
                continue
                
            # Split page text into segments
            segments = chunk_text(page_text, chunk_size=1000, overlap=150)
            
            for chunk_idx, segment in enumerate(segments):
                # Prefix segment with section path to prevent embedding semantic drift
                path_prefix = f"Section: {section_path}\n\n" if section_path else ""
                annotated_text = f"{path_prefix}{segment}"
                
                # Tag chunk with concepts contained and affected metrics
                concepts = []
                affected_metrics = []
                text_lower = annotated_text.lower()
                
                if "revenue" in text_lower:
                    concepts.append("Revenue")
                    affected_metrics.append("ebitda_margin")
                if "ebitda" in text_lower:
                    concepts.append("EBITDA")
                    affected_metrics.extend(["net_debt_to_ebitda", "ebitda_margin", "interest_coverage"])
                if "debt" in text_lower:
                    concepts.append("Total Debt")
                    affected_metrics.extend(["net_debt", "net_debt_to_ebitda"])
                if "cash" in text_lower:
                    concepts.append("Cash")
                    affected_metrics.extend(["net_debt", "net_debt_to_ebitda"])
                if "interest" in text_lower:
                    concepts.append("Interest Expense")
                    affected_metrics.append("interest_coverage")
                    
                chunk_meta = {
                    "fiscal_year": fiscal_year,
                    "fiscal_period": fiscal_period,
                    "concepts_contained": list(set(concepts)),
                    "affected_metrics": list(set(affected_metrics))
                }
                
                # Generate OpenAI 1536 embedding using text-embedding-3-small
                response = openai_client.embeddings.create(
                    model="text-embedding-3-small",
                    input=annotated_text
                )
                embedding_vector = response.data[0].embedding
                
                # Save DocumentChunk
                db_chunk = DocumentChunk(
                    company_id=company_id,
                    document_id=document_id,
                    page_number=page_num,
                    displayed_page_number=displayed_page_number,
                    section_path=section_path,
                    chunk_index=chunk_idx,
                    text_content=annotated_text,
                    embedding=embedding_vector,
                    chunk_metadata=chunk_meta
                )
                db.add(db_chunk)
                saved_chunks_count += 1
                
        db.commit()
        logger.info(f"Successfully saved {saved_chunks_count} chunks to database.")
        return {"status": "success", "chunks_indexed": saved_chunks_count}
        
    except Exception as e:
        db.rollback()
        logger.exception(f"Error during document indexing: {e}")
        raise e
    finally:
        db.close()
