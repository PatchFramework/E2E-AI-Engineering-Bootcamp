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
    AuditEvent, DataQualityIssue,
    DerivedMetricDefinition, DerivedMetricValue, DerivedMetricInputFact
)
from api.schemas.schemas import (
    CompanyResponse, CompanyCreate,
    FinancialFactResponse, FinancialFactCorrectionRequest,
    ChatMessage, ChatSessionRequest,
    DocumentResponse, DataQualityIssueResponse,
    CompanyMetricResponse, MetricHistoryPoint, MetricLineageResponse,
    FactCorrectionResponse
)
from api.core.metric_registry import METRIC_REGISTRY
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


@api_router.get("/documents/{document_id}/file", tags=["Documents"])
async def get_document_file(document_id: int, db: Session = Depends(get_db)):
    """
    Streams the entire original document file from S3.
    """
    doc_record = db.query(Document).filter(Document.id == document_id).first()
    if not doc_record:
        doc_record = db.query(Document).order_by(Document.id.desc()).first()
    if not doc_record:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        pdf_bytes = StorageService.download_file(doc_record.s3_path)
        filename = doc_record.filename or f"document_{doc_record.id}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{filename}"'}
        )
    except Exception as e:
        logger.exception(f"Failed to fetch document file from S3: {e}")
        raise HTTPException(status_code=404, detail=f"File not found in storage: {e}")


@api_router.get("/documents/{document_id}/pages/{page_number}", tags=["Documents"])
async def get_document_page_image(document_id: int, page_number: int, db: Session = Depends(get_db)):
    """
    Returns the page image as PNG.
    If cached in MinIO, serves it directly.
    Else, renders it on-the-fly from the original PDF and caches it.
    """
    # 1. Try loading direct cached page image from S3
    s3_key = f"pages/{document_id}/page_{page_number}.png"
    try:
        image_bytes = StorageService.download_file(s3_key)
        return Response(content=image_bytes, media_type="image/png")
    except Exception:
        pass

    # 2. Fallback: Lookup document record in database
    doc_record = db.query(Document).filter(Document.id == document_id).first()
    if not doc_record:
        # Fallback to first available document
        doc_record = db.query(Document).order_by(Document.id.desc()).first()
        if doc_record:
            try:
                fallback_s3_key = f"pages/{doc_record.id}/page_{page_number}.png"
                image_bytes = StorageService.download_file(fallback_s3_key)
                return Response(content=image_bytes, media_type="image/png")
            except Exception:
                pass

    if not doc_record:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        pdf_bytes = StorageService.download_file(doc_record.s3_path)
        pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        # Clamp page number within valid PDF range
        target_page = max(1, min(len(pdf_doc), page_number))
        page = pdf_doc[target_page - 1]
        pix = page.get_pixmap(dpi=150)
        image_bytes = pix.tobytes("png")
        pdf_doc.close()
        
        # Cache the rendered page back to MinIO
        try:
            StorageService.upload_file(image_bytes, f"pages/{doc_record.id}/page_{page_number}.png", content_type="image/png")
        except Exception:
            pass
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


def get_affected_metrics_for_concept(concept: str) -> List[str]:
    """
    Returns the list of metric display names whose formulas depend on the given concept.
    """
    affected = []
    norm_c = concept.strip().lower().replace(" ", "_").replace("-", "_")
    
    # Map common aliases
    concept_aliases = [norm_c]
    if norm_c == "ebitda":
        concept_aliases.extend(["ebitda"])
    elif norm_c in ["operating_income", "ebit"]:
        concept_aliases.extend(["operating_income", "ebit"])
    elif norm_c in ["capital_expenditures", "capex"]:
        concept_aliases.extend(["capital_expenditures", "capex"])
    elif norm_c in ["total_debt", "short_term_debt", "long_term_debt"]:
        concept_aliases.extend(["total_debt", "short_term_debt", "long_term_debt"])

    for key, cfg in METRIC_REGISTRY.items():
        req_norm = [rc.strip().lower().replace(" ", "_").replace("-", "_") for rc in cfg.required_concepts]
        if any(alias in req_norm for alias in concept_aliases):
            if cfg.display_name not in affected:
                affected.append(cfg.display_name)
                
    if "Suggested Rating" not in affected:
        affected.append("Suggested Rating")
    return affected


@api_router.post("/facts/{fact_id}/verify", response_model=FinancialFactResponse, tags=["Facts"])
async def verify_financial_fact(fact_id: int, db: Session = Depends(get_db)):
    """
    Marks an active financial fact as VERIFIED, logs an audit event,
    and recalculates derived KPIs.
    """
    fact = db.query(FinancialFact).filter(FinancialFact.id == fact_id).first()
    if not fact:
        raise HTTPException(status_code=404, detail="Financial fact not found")

    version = db.query(FinancialFactVersion).filter(
        FinancialFactVersion.fact_id == fact_id,
        FinancialFactVersion.is_current == True
    ).first()
    if not version:
        raise HTTPException(status_code=404, detail="Active fact version not found")

    if version.verification_status != "VERIFIED":
        version.verification_status = "VERIFIED"
        audit_event = AuditEvent(
            actor="analyst",
            action="FACT_VERIFIED",
            entity_type="financial_fact",
            entity_id=fact_id,
            company_id=fact.company_id,
            previous_value=str(version.value),
            new_value=str(version.value),
            reason="Verified by analyst"
        )
        db.add(audit_event)
        try:
            db.commit()
            db.refresh(version)
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to verify fact: {e}")

        # Recalculate metrics
        try:
            MetricCalculationService.recalculate_metrics_for_period(
                db,
                company_id=fact.company_id,
                year=fact.fiscal_year,
                period=fact.fiscal_period
            )
        except Exception as e:
            logger.error(f"Derived metrics recalculation failed after fact verification: {e}")

    return FinancialFactResponse(
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


@api_router.post("/facts/{fact_id}/correct", response_model=FactCorrectionResponse, tags=["Facts"])
async def correct_financial_fact(fact_id: int, payload: FinancialFactCorrectionRequest, db: Session = Depends(get_db)):
    """
    Corrects a financial fact value, deactivating the old version, creating a new
    version with VERIFIED status, and triggering synchronous derived KPI recalculations.
    Returns the updated fact and the list of affected metrics.
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

    affected_metrics = get_affected_metrics_for_concept(fact.concept)

    fact_resp = FinancialFactResponse(
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
    return FactCorrectionResponse(fact=fact_resp, affected_metrics=affected_metrics)


# Derived Metrics Router
@api_router.get("/companies/{company_id}/metrics", response_model=List[CompanyMetricResponse], tags=["Metrics"])
async def get_company_metrics(
    company_id: int,
    fiscal_year: Optional[int] = None,
    fiscal_period: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Returns calculated derived metrics for a company across all 6 financial categories,
    including current values, prior year values, YoY deltas, and historical time-series points.
    """
    # 1. Determine target fiscal year if not explicitly passed
    if fiscal_year is None:
        latest_fact = db.query(FinancialFact).filter(
            FinancialFact.company_id == company_id
        ).order_by(FinancialFact.fiscal_year.desc()).first()

        latest_metric = db.query(DerivedMetricValue).filter(
            DerivedMetricValue.company_id == company_id
        ).order_by(DerivedMetricValue.fiscal_year.desc()).first()

        latest_fact_year = latest_fact.fiscal_year if latest_fact else None
        latest_metric_year = latest_metric.fiscal_year if latest_metric else None

        if latest_fact_year and latest_metric_year:
            fiscal_year = max(latest_fact_year, latest_metric_year)
        elif latest_fact_year:
            fiscal_year = latest_fact_year
        elif latest_metric_year:
            fiscal_year = latest_metric_year
        else:
            fiscal_year = 2025

    if fiscal_period is None:
        # Detect active period from facts for this year
        fact_for_year = db.query(FinancialFact).filter(
            FinancialFact.company_id == company_id,
            FinancialFact.fiscal_year == fiscal_year
        ).first()
        fiscal_period = fact_for_year.fiscal_period if fact_for_year else "FY"

    # 2. Check if metrics are already calculated for target year with AVAILABLE status
    available_metrics_count = db.query(DerivedMetricValue).filter(
        DerivedMetricValue.company_id == company_id,
        DerivedMetricValue.fiscal_year == fiscal_year,
        DerivedMetricValue.status == "AVAILABLE"
    ).count()

    if available_metrics_count == 0:
        try:
            MetricCalculationService.recalculate_metrics_for_period(
                db, company_id=company_id, year=fiscal_year, period=fiscal_period
            )
            # Also calculate for other years if facts exist
            all_years = db.query(FinancialFact.fiscal_year, FinancialFact.fiscal_period).filter(
                FinancialFact.company_id == company_id
            ).distinct().all()
            for (yr, prd) in all_years:
                if yr != fiscal_year:
                    MetricCalculationService.recalculate_metrics_for_period(
                        db, company_id=company_id, year=yr, period=prd or "FY"
                    )
        except Exception as ex:
            logger.warning(f"Auto-recalculation of metrics during fetch encountered warning: {ex}")

    # 3. Query all derived metrics for this company
    all_metric_values = db.query(DerivedMetricValue).filter(
        DerivedMetricValue.company_id == company_id
    ).all()

    # Group metric values by metric_name -> list of records
    metric_values_by_name: dict[str, list[DerivedMetricValue]] = {}
    for val in all_metric_values:
        metric_values_by_name.setdefault(val.metric_name, []).append(val)

    # 4. Fetch definitions from DB or sync
    definitions = {d.metric_name: d for d in db.query(DerivedMetricDefinition).all()}

    response_list: List[CompanyMetricResponse] = []

    for metric_name, cfg in METRIC_REGISTRY.items():
        records = metric_values_by_name.get(metric_name, [])
        
        # Deduplicate records by fiscal_year, preferring AVAILABLE records
        year_to_record: dict[int, DerivedMetricValue] = {}
        for r in records:
            if r.fiscal_year not in year_to_record or (r.status == "AVAILABLE" and year_to_record[r.fiscal_year].status != "AVAILABLE"):
                year_to_record[r.fiscal_year] = r

        curr_record = year_to_record.get(fiscal_year)
        prior_record = year_to_record.get(fiscal_year - 1)

        curr_val = curr_record.value if (curr_record and curr_record.status == "AVAILABLE") else None
        prior_val = prior_record.value if (prior_record and prior_record.status == "AVAILABLE") else None

        yoy_change = None
        yoy_change_pct = None
        trend = "neutral"

        if curr_val is not None and prior_val is not None:
            yoy_change = curr_val - prior_val
            if prior_val != 0:
                yoy_change_pct = (curr_val - prior_val) / abs(prior_val) * 100
            if yoy_change > 0.0001:
                trend = "up"
            elif yoy_change < -0.0001:
                trend = "down"

        # Determine verification status from input facts
        ver_status = "UNVERIFIED"
        if curr_record and curr_record.input_facts:
            roles_ver = [link.fact_version.verification_status for link in curr_record.input_facts if link.fact_version]
            origins = [link.fact_version.origin for link in curr_record.input_facts if link.fact_version]
            if any(o == "ANALYST_CORRECTED" for o in origins):
                ver_status = "CORRECTED"
            elif roles_ver and all(v == "VERIFIED" for v in roles_ver):
                ver_status = "VERIFIED"
            else:
                ver_status = "UNVERIFIED"
        elif curr_record and curr_record.status != "AVAILABLE":
            ver_status = "UNAVAILABLE"

        # Build unique, sorted history points
        history_points: List[MetricHistoryPoint] = []
        for yr in sorted(year_to_record.keys()):
            r = year_to_record[yr]
            history_points.append(MetricHistoryPoint(
                fiscal_year=r.fiscal_year,
                fiscal_period=r.fiscal_period,
                value=r.value if r.status == "AVAILABLE" else None,
                status=r.status
            ))

        db_def = definitions.get(metric_name)

        metric_resp = CompanyMetricResponse(
            id=curr_record.id if curr_record else None,
            metric_name=metric_name,
            display_name=cfg.display_name,
            category=cfg.category,
            formula_expression=cfg.formula_expression,
            unit=cfg.unit,
            description=cfg.description,
            current_value=curr_val,
            prior_value=prior_val,
            yoy_change=yoy_change,
            yoy_change_pct=yoy_change_pct,
            trend=trend,
            verification_status=ver_status,
            status=curr_record.status if curr_record else ("AVAILABLE" if curr_val is not None else "UNAVAILABLE"),
            status_reason=curr_record.status_reason if curr_record else None,
            fiscal_year=fiscal_year,
            fiscal_period=fiscal_period,
            calculated_at=curr_record.calculated_at if curr_record else None,
            history=history_points
        )
        response_list.append(metric_resp)

    return response_list



@api_router.get("/metrics/{derived_metric_id}/lineage", response_model=MetricLineageResponse, tags=["Metrics"])
async def get_metric_lineage(derived_metric_id: int, db: Session = Depends(get_db)):
    """
    Returns full evidence provenance and input lineage for a calculated derived metric.
    """
    lineage = MetricCalculationService.get_metric_lineage(db, derived_metric_id)
    if not lineage:
        raise HTTPException(status_code=404, detail="Derived metric not found or has no calculation lineage.")
    return lineage



from api.copilot.schemas.citation_schemas import CitationSource
from api.routers.copilot import copilot_router

# Include Copilot sub-router
api_router.include_router(copilot_router)

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
