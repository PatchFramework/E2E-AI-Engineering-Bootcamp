from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

# Company Schemas
class CompanyBase(BaseModel):
    name: str
    ticker: Optional[str] = None

class CompanyCreate(CompanyBase):
    pass

class CompanyResponse(CompanyBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# Financial Fact Schemas
class FinancialFactBase(BaseModel):
    company_id: int
    concept: str = Field(..., description="Canonical concept name (e.g., EBITDA, Revenue)")
    value: float
    unit: str = Field("EUR", description="E.g., EUR, USD, ratio, percentage")
    fiscal_year: int
    fiscal_period: str = Field("FY", description="E.g., FY, Q1, Q2, Q3, Q4")

class FinancialFactCorrectionRequest(BaseModel):
    value: float
    change_reason: str = Field(..., description="Reason for override/correction by analyst")

class FinancialFactResponse(FinancialFactBase):
    id: int
    version: int
    origin: str = Field("AI_GENERATED", description="AI_GENERATED, ANALYST_CORRECTED, ANALYST_ENTERED")
    verification_status: str = Field("UNVERIFIED", description="UNVERIFIED, VERIFIED")
    updated_at: datetime

    class Config:
        from_attributes = True

# Copilot / Agent Schemas
class ChatMessage(BaseModel):
    role: str = Field(..., description="user or assistant")
    content: str

class ChatSessionRequest(BaseModel):
    query: str
    thread_id: str
    company_id: int


# Document Schemas
class DocumentResponse(BaseModel):
    id: int
    company_id: int
    filename: str
    s3_path: str
    content_hash: str
    fiscal_year: Optional[int] = None
    fiscal_period: Optional[str] = None
    document_type: Optional[str] = None
    created_at: datetime
    dag_run_id: Optional[str] = None  # Airflow pipeline run ID for status polling

    class Config:
        from_attributes = True


# Data Quality Issue Schemas
class DataQualityIssueResponse(BaseModel):
    id: int
    company_id: int
    document_id: Optional[int] = None
    issue_type: str
    severity: str
    concept: Optional[str] = None
    message: str
    is_resolved: bool
    created_at: datetime

    class Config:
        from_attributes = True


# Derived Metrics & Lineage Schemas
class MetricHistoryPoint(BaseModel):
    fiscal_year: int
    fiscal_period: str
    value: Optional[float] = None
    status: str = "AVAILABLE"


class CompanyMetricResponse(BaseModel):
    id: Optional[int] = None
    metric_name: str
    display_name: str
    category: str
    formula_expression: Optional[str] = None
    unit: str = "ratio"
    description: Optional[str] = None
    current_value: Optional[float] = None
    prior_value: Optional[float] = None
    yoy_change: Optional[float] = None
    yoy_change_pct: Optional[float] = None
    trend: str = "neutral"  # up, down, neutral
    verification_status: str = "UNVERIFIED"  # VERIFIED, CORRECTED, UNVERIFIED, UNAVAILABLE
    status: str = "AVAILABLE"  # AVAILABLE, UNAVAILABLE, ERROR
    status_reason: Optional[str] = None
    fiscal_year: int
    fiscal_period: str = "FY"
    calculated_at: Optional[datetime] = None
    history: List[MetricHistoryPoint] = []


class SourceLocationSchema(BaseModel):
    location_id: Optional[int] = None
    page_number: Optional[int] = None
    displayed_page_number: Optional[str] = None
    section: Optional[str] = None
    section_path: Optional[str] = None
    text_snippet: Optional[str] = None
    bounding_box: Optional[Any] = None


class DocumentInfoSchema(BaseModel):
    document_id: Optional[int] = None
    filename: Optional[str] = None
    s3_path: Optional[str] = None
    fiscal_year: Optional[int] = None
    fiscal_period: Optional[str] = None


class MetricInputFactLineage(BaseModel):
    fact_id: Optional[int] = None
    fact_version_id: Optional[int] = None
    concept: str
    role: str
    value: Optional[float] = None
    unit: str = "EUR"
    origin: Optional[str] = None
    verification_status: Optional[str] = None
    source_location: Optional[SourceLocationSchema] = None
    document: Optional[DocumentInfoSchema] = None


class MetricCitedChunk(BaseModel):
    chunk_id: int
    document_id: int
    page_number: int
    displayed_page_number: Optional[str] = None
    section_path: Optional[str] = None
    text_content: str
    chunk_metadata: Optional[Dict[str, Any]] = None


class MetricLineageResponse(BaseModel):
    derived_metric_id: int
    metric_name: str
    display_name: str
    category: str
    formula_expression: Optional[str] = None
    value: Optional[float] = None
    unit: str = "ratio"
    status: str
    status_reason: Optional[str] = None
    fiscal_year: int
    fiscal_period: str
    calculated_at: Optional[str] = None
    input_facts: List[MetricInputFactLineage] = []
    cited_chunks: List[MetricCitedChunk] = []


class FactCorrectionResponse(BaseModel):
    fact: FinancialFactResponse
    affected_metrics: List[str] = []


