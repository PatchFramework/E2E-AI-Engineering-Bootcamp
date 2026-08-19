import logging
import hashlib
from typing import Dict, Any, List, Literal, Optional
from pydantic import BaseModel, Field
from openai import OpenAI
import instructor

from sqlalchemy import func
from api.core.config import config
from api.core.database import SessionLocal
from api.models.db_models import Document, FinancialFact, FinancialFactVersion, SourceLocation

logger = logging.getLogger("pipelines.tasks.extraction")

# Define the structured output schemas
class ExtractedFact(BaseModel):
    concept: Literal[
        "Revenue", "Cost of Goods Sold", "Gross Profit", "Operating Expense",
        "Operating Income", "EBITDA", "Net Income", "Total Debt", "Cash",
        "Current Assets", "Current Liabilities", "Total Equity",
        "Operating Cash Flow", "Capital Expenditures", "Total Assets",
        "Total Liabilities", "Interest Expense", "Short-term Debt",
        "Long-term Debt", "Short-term Investments", "Receivables",
        "Working Capital", "Free Cash Flow"
    ] = Field(..., description="Canonical concept name from the allowed list")
    value: float = Field(..., description="The numerical value extracted from the text (convert raw strings like '$1.2B' to 1200000000.0)")
    unit: str = Field("EUR", description="The unit of the value, e.g. EUR, USD, etc. (normalize to ISO currency codes)")
    location_id: str = Field(..., description="The exact ID of the text block where the value was found (e.g. p1_b5)")


class ExtractedFactsList(BaseModel):
    facts: List[ExtractedFact]


def extract_facts(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extracts financial facts from the parsed PDF layout text using structured LLM output.
    Saves the facts and versions into the database.
    """
    document_id = parsed_data["document_id"]
    company_id = parsed_data["company_id"]
    
    logger.info(f"Starting financial fact extraction for document_id {document_id}")
    
    # 1. Fetch document metadata from database (to get fiscal year and period)
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise ValueError(f"Document with ID {document_id} not found in database.")
        
        fiscal_year = doc.fiscal_year
        fiscal_period = doc.fiscal_period
        
        # 2. Format the text blocks for the LLM
        formatted_blocks = []
        for page in parsed_data["pages"]:
            page_num = page["page_number"]
            section_path = page["section_path"]
            for block in page["blocks"]:
                block_id = block["id"]
                block_text = block["text"]
                formatted_blocks.append(
                    f"[Block ID: {block_id}] [Section: {section_path}] Page {page_num}: {block_text}"
                )
        
        full_payload_text = "\n".join(formatted_blocks)
        
        # 3. Call OpenAI using instructor
        openai_client = OpenAI(api_key=config.OPENAI_API_KEY)
        instructor_client = instructor.from_openai(openai_client)
        
        logger.info("Calling OpenAI for structured financial concept extraction...")
        extracted: ExtractedFactsList = instructor_client.chat.completions.create(
            model="gpt-4o-mini",
            response_model=ExtractedFactsList,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a credit underwriting engine. Extract financial facts from the corporate filing. "
                        "Map each fact to one of the canonical concepts:\n"
                        "- Revenue\n- EBITDA\n- Operating Income\n- Interest Expense\n- Total Debt\n- Cash\n"
                        "- Net Income\n- Total Assets\n- Total Liabilities\n- Total Equity\n\n"
                        "For each fact, output its canonical concept, normalized numerical value (as float, handling scales like millions/billions), "
                        "unit, and the exact [Block ID] where the text occurs. Do not invent facts."
                    )
                },
                {
                    "role": "user",
                    "content": f"Extract facts from the following filing text:\n\n{full_payload_text}"
                }
            ],
            temperature=0.0,
            max_retries=3
        )
        
        logger.info(f"Successfully extracted {len(extracted.facts)} facts from LLM.")
        
        # 4. Save facts and versions to database
        saved_fact_ids = []
        for fact_item in extracted.facts:
            # Find the corresponding text block in parsed_data to get bounding boxes & text snippet
            block_detail = None
            page_detail = None
            for p in parsed_data["pages"]:
                for b in p["blocks"]:
                    if b["id"] == fact_item.location_id:
                        block_detail = b
                        page_detail = p
                        break
                if block_detail:
                    break
            
            if not block_detail:
                logger.warning(f"Could not find block metadata for location_id {fact_item.location_id}. Skipping.")
                continue
            
            # Create or find SourceLocation
            content_hash = hashlib.sha256(block_detail["text"].encode("utf-8")).hexdigest()
            source_loc = db.query(SourceLocation).filter(
                SourceLocation.document_id == document_id,
                SourceLocation.content_hash == content_hash
            ).first()
            
            if not source_loc:
                source_loc = SourceLocation(
                    document_id=document_id,
                    page_number=page_detail["page_number"],
                    displayed_page_number=page_detail["displayed_page_number"],
                    section=page_detail["section_path"].split(" > ")[-1] if page_detail["section_path"] else None,
                    section_path=page_detail["section_path"],
                    text_snippet=block_detail["text"],
                    bounding_box=block_detail["bbox"],
                    content_hash=content_hash
                )
                db.add(source_loc)
                db.flush()  # Populates source_loc.id
                
            # Create or find FinancialFact
            financial_fact = db.query(FinancialFact).filter(
                FinancialFact.company_id == company_id,
                FinancialFact.concept == fact_item.concept,
                FinancialFact.fiscal_year == fiscal_year,
                FinancialFact.fiscal_period == fiscal_period
            ).first()
            
            if not financial_fact:
                financial_fact = FinancialFact(
                    company_id=company_id,
                    concept=fact_item.concept,
                    fiscal_year=fiscal_year,
                    fiscal_period=fiscal_period
                )
                db.add(financial_fact)
                db.flush()  # Populates financial_fact.id
                
            # Deactivate previous active versions of this fact if they exist
            db.query(FinancialFactVersion).filter(
                FinancialFactVersion.fact_id == financial_fact.id,
                FinancialFactVersion.is_current == True
            ).update({"is_current": False})
            
            # Find next version number
            latest_ver = db.query(func.max(FinancialFactVersion.version)).filter(
                FinancialFactVersion.fact_id == financial_fact.id
            ).scalar()
            next_ver = (latest_ver or 0) + 1
            
            # Create new FinancialFactVersion
            fact_version = FinancialFactVersion(
                fact_id=financial_fact.id,
                version=next_ver,
                value=fact_item.value,
                unit=fact_item.unit,
                origin="AI_GENERATED",
                verification_status="UNVERIFIED",
                source_location_id=source_loc.id,
                is_current=True
            )
            db.add(fact_version)
            db.flush()
            
            saved_fact_ids.append(financial_fact.id)
            
        db.commit()
        logger.info(f"Persisted {len(saved_fact_ids)} financial facts into database.")
        
        return {
            "document_id": document_id,
            "company_id": company_id,
            "fiscal_year": fiscal_year,
            "fiscal_period": fiscal_period,
            "fact_ids": saved_fact_ids
        }
        
    except Exception as e:
        db.rollback()
        logger.exception(f"Error persisting extracted financial facts: {e}")
        raise e
    finally:
        db.close()
