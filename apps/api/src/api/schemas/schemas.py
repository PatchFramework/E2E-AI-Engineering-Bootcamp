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

