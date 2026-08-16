import fitz  # PyMuPDF
import hashlib
import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import func

from api.core.database import get_db
from api.models.db_models import (
    Company, Document, FinancialFact, FinancialFactVersion,
    AuditEvent, DataQualityIssue
)
from api.schemas.schemas import (
    CompanyResponse, CompanyCreate,
    FinancialFactResponse, FinancialFactCorrectionRequest,
    ChatMessage, ChatSessionRequest,
    DocumentResponse, DataQualityIssueResponse
)
from api.services.storage_service import StorageService
from api.services.metadata_extraction_service import MetadataExtractionService
from api.services.airflow_service import AirflowService
from api.services.metric_calculation import MetricCalculationService

logger = logging.getLogger("api.routers.endpoints")
api_router = APIRouter()

# Companies Router
@api_router.get("/companies", response_model=List[CompanyResponse], tags=["Companies"])
async def get_companies(db: Session = Depends(get_db)):
    """
    Returns all registered companies.
    """
    return db.query(Company).order_by(Company.name).all()


@api_router.post("/companies", response_model=CompanyResponse, tags=["Companies"])
async def create_company(payload: CompanyCreate, db: Session = Depends(get_db)):
    """
    Creates a new company if it doesn't already exist.
    """
    company_name_cleaned = payload.name.strip()
    existing = db.query(Company).filter(func.lower(Company.name) == company_name_cleaned.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Company with this name already exists")
    
    company = Company(name=company_name_cleaned, ticker=payload.ticker)
    db.add(company)
    try:
        db.commit()
        db.refresh(company)
        return company
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create company: {e}")


@api_router.get("/companies/{company_id}/quality-issues", response_model=List[DataQualityIssueResponse], tags=["Companies"])
async def get_company_quality_issues(company_id: int, db: Session = Depends(get_db)):
    """
    Returns all unresolved quality issues for a given company.
    """
    return db.query(DataQualityIssue).filter(
        DataQualityIssue.company_id == company_id,
        DataQualityIssue.is_resolved == False
    ).all()


# Documents Router
@api_router.post("/documents/upload", response_model=DocumentResponse, tags=["Documents"])
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Uploads a filing PDF, extracts metadata on the fly, checks for duplicates,
    saves the document, and triggers the Airflow data pipeline.
    """
    # 1. Read file bytes
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # 2. Check for duplicate content hash
    content_hash = hashlib.sha256(file_bytes).hexdigest()
    existing_doc = db.query(Document).filter(Document.content_hash == content_hash).first()
    if existing_doc:
        logger.info(f"Duplicate document uploaded (hash={content_hash}). Bypassing Airflow trigger.")
        return existing_doc

    # 3. Extract metadata using LLM (gpt-4o-mini)
    try:
        metadata = MetadataExtractionService.extract_metadata(file_bytes)
    except Exception as e:
        logger.error(f"Error during metadata extraction: {e}")
        raise HTTPException(status_code=400, detail=f"Could not extract metadata from filing: {e}")

    # 4. Find or create company
    company_name = metadata.company_name.strip()
    company = db.query(Company).filter(func.lower(Company.name) == company_name.lower()).first()
    if not company:
        logger.info(f"Company '{company_name}' not found. Creating new company.")
        company = Company(name=company_name)
        db.add(company)
        db.commit()
        db.refresh(company)

    # 5. Upload document to MinIO under structured path
    # filings/{company_id}/{fiscal_year}_{fiscal_period}/{document_type}_{content_hash}.pdf
    s3_key = f"filings/{company.id}/{metadata.fiscal_year}_{metadata.fiscal_period}/{metadata.document_type}_{content_hash}.pdf"
    try:
        StorageService.upload_file(file_bytes, s3_key, content_type="application/pdf")
    except Exception as e:
        logger.exception(f"Failed to upload document to MinIO: {e}")
        raise HTTPException(status_code=500, detail="Failed to save document to object storage.")

    # 6. Create Document record in DB
    document = Document(
        company_id=company.id,
        filename=file.filename,
        s3_path=s3_key,
        content_hash=content_hash,
        fiscal_year=metadata.fiscal_year,
        fiscal_period=metadata.fiscal_period,
        document_type=metadata.document_type
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    # 7. Trigger Airflow ingestion pipeline
    dag_run_id = AirflowService.trigger_financial_ingestion(
        document_id=document.id,
        company_id=company.id,
        fiscal_year=metadata.fiscal_year,
        fiscal_period=metadata.fiscal_period,
        document_type=metadata.document_type,
        s3_path=s3_key,
        content_hash=content_hash
    )
    if not dag_run_id:
        logger.error("Failed to trigger Airflow data pipeline DAG.")
        try:
            db.delete(document)
            db.commit()
        except Exception as delete_ex:
            logger.error(f"Failed to delete document after Airflow trigger failure: {delete_ex}")
            db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to trigger the processing pipeline. Ingestion could not be started."
        )
    else:
        logger.info(f"Triggered Airflow pipeline run: {dag_run_id}")

    # Return document with dag_run_id for frontend status polling
    return DocumentResponse(
        id=document.id,
        company_id=document.company_id,
        filename=document.filename,
        s3_path=document.s3_path,
        content_hash=document.content_hash,
        fiscal_year=document.fiscal_year,
        fiscal_period=document.fiscal_period,
        document_type=document.document_type,
        created_at=document.created_at,
        dag_run_id=dag_run_id,
    )


@api_router.get("/documents/{document_id}", response_model=DocumentResponse, tags=["Documents"])
async def get_document(document_id: int, db: Session = Depends(get_db)):
    """
    Returns document details by ID.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@api_router.get("/documents/{document_id}/pages/{page_number}", tags=["Documents"])
async def get_document_page_image(document_id: int, page_number: int, db: Session = Depends(get_db)):
    """
    Returns the page image as PNG.
    If cached in MinIO, serves it directly.
    Else, renders it on-the-fly from the original PDF and caches it.
    """
    s3_key = f"pages/{document_id}/page_{page_number}.png"
    # Try loading cached page image from S3
    try:
        image_bytes = StorageService.download_file(s3_key)
        return Response(content=image_bytes, media_type="image/png")
    except Exception:
        # Fallback: render on the fly from original PDF
        doc_record = db.query(Document).filter(Document.id == document_id).first()
        if not doc_record:
            raise HTTPException(status_code=404, detail="Document not found")
        try:
            pdf_bytes = StorageService.download_file(doc_record.s3_path)
            pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            # validate page number
            if page_number < 1 or page_number > len(pdf_doc):
                pdf_doc.close()
                raise HTTPException(status_code=404, detail=f"Page {page_number} is out of range for this document")
            
            page = pdf_doc[page_number - 1]
            pix = page.get_pixmap(dpi=150)
            image_bytes = pix.tobytes("png")
            pdf_doc.close()
            
            # Cache the rendered page back to MinIO asynchronously or synchronously
            StorageService.upload_file(image_bytes, s3_key, content_type="image/png")
            return Response(content=image_bytes, media_type="image/png")
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Failed to render PDF page on-the-fly: {e}")
            raise HTTPException(status_code=404, detail=f"Page could not be rendered: {e}")


# Financial Facts Router
@api_router.get("/facts/{company_id}", response_model=List[FinancialFactResponse], tags=["Facts"])
async def get_financial_facts(company_id: int, db: Session = Depends(get_db)):
    """
    Returns all current active financial facts for a given company.
    """
    results = db.query(FinancialFact, FinancialFactVersion).join(
        FinancialFactVersion, FinancialFact.id == FinancialFactVersion.fact_id
    ).filter(
        FinancialFact.company_id == company_id,
        FinancialFactVersion.is_current == True
    ).all()
    
    response = []
    for fact, version in results:
        response.append(
            FinancialFactResponse(
                id=fact.id,
                company_id=fact.company_id,
                concept=fact.concept,
                value=version.value,
                unit=version.unit,
                fiscal_year=fact.fiscal_year,
                fiscal_period=fact.fiscal_period,
                version=version.version,
                origin=version.origin,
                verification_status=version.verification_status,
                updated_at=version.created_at
            )
        )
    return response


@api_router.post("/facts/{fact_id}/correct", response_model=FinancialFactResponse, tags=["Facts"])
async def correct_financial_fact(fact_id: int, payload: FinancialFactCorrectionRequest, db: Session = Depends(get_db)):
    """
    Corrects a financial fact value, deactivating the old version, creating a new
    version with VERIFIED status, and triggering synchronous derived KPI recalculations.
    """
    # 1. Fetch existing fact
    fact = db.query(FinancialFact).filter(FinancialFact.id == fact_id).first()
    if not fact:
        raise HTTPException(status_code=404, detail="Financial fact not found")

    # 2. Get current active version
    old_version = db.query(FinancialFactVersion).filter(
        FinancialFactVersion.fact_id == fact_id,
        FinancialFactVersion.is_current == True
    ).first()
    if not old_version:
        raise HTTPException(status_code=404, detail="Active fact version not found")

    # 3. Deactivate old version
    old_version.is_current = False

    # 4. Create new version
    new_version = FinancialFactVersion(
        fact_id=fact_id,
        version=old_version.version + 1,
        value=payload.value,
        unit=old_version.unit,
        origin="ANALYST_CORRECTED",
        verification_status="VERIFIED",
        change_reason=payload.change_reason,
        is_current=True,
        created_by="analyst"
    )
    db.add(new_version)

    # 5. Create Audit Event
    audit_event = AuditEvent(
        actor="analyst",
        action="FACT_CORRECTED",
        entity_type="financial_fact",
        entity_id=fact_id,
        company_id=fact.company_id,
        previous_value=str(old_version.value),
        new_value=str(payload.value),
        reason=payload.change_reason
    )
    db.add(audit_event)

    try:
        db.commit()
        db.refresh(new_version)
    except Exception as e:
        db.rollback()
        logger.exception(f"Failed to commit fact correction for fact_id {fact_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to save fact correction.")

    # 6. Recalculate derived metrics for period synchronously
    try:
        MetricCalculationService.recalculate_metrics_for_period(
            db,
            company_id=fact.company_id,
            year=fact.fiscal_year,
            period=fact.fiscal_period
        )
    except Exception as e:
        logger.error(f"Derived metrics recalculation failed: {e}")
        # Note: We still return success since the database transaction was committed.

    return FinancialFactResponse(
        id=fact.id,
        company_id=fact.company_id,
        concept=fact.concept,
        value=new_version.value,
        unit=new_version.unit,
        fiscal_year=fact.fiscal_year,
        fiscal_period=fact.fiscal_period,
        version=new_version.version,
        origin=new_version.origin,
        verification_status=new_version.verification_status,
        updated_at=new_version.created_at
    )


# Copilot Agent Router
@api_router.post("/copilot/chat", tags=["Copilot"])
async def copilot_chat(payload: ChatSessionRequest):
    # This will route to the LangGraph copilot agent
    return {"answer": "I am the Credit Underwriting Copilot. Please ask questions about corporate filings.", "citations": []}


# Pipeline Status Router
@api_router.get("/pipeline/status/{dag_run_id}", tags=["Pipeline"])
async def get_pipeline_status(dag_run_id: str):
    """
    Returns the current state of an Airflow DAG run and all its task instances.
    Used by the frontend to non-blockingly poll job status after document upload.

    DAG states: queued | running | success | failed
    Task states: queued | running | success | failed | upstream_failed | skipped
    """
    status = AirflowService.get_dag_run_status(dag_run_id)
    if not status:
        raise HTTPException(
            status_code=404,
            detail=f"Pipeline run '{dag_run_id}' not found or Airflow is unreachable."
        )
    return status
