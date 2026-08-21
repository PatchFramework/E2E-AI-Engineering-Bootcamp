from typing import List, Optional, Literal
from pydantic import BaseModel, Field

class CitationSource(BaseModel):
    document_id: int = Field(..., description="PostgreSQL Document ID")
    filename: str = Field(..., description="Filing PDF filename (e.g., 'FY2025_Annual_Report.pdf')")
    page_number: int = Field(..., description="Physical 1-based PDF page index for renderer navigation")
    displayed_page: str = Field(..., description="Human-readable printed page label (e.g., 'p. 42')")
    section: Optional[str] = Field(None, description="Filing section path (e.g., 'Note 18: Borrowings')")
    snippet: Optional[str] = Field(None, description="Verbatim cited text excerpt or numerical evidence")
    bounding_box: Optional[List[float]] = Field(None, description="[x0, top, x1, bottom] coordinates for PDF highlight overlay")
    confidence_score: Optional[float] = Field(None, description="Retrieval similarity score or fact verification weight")
    source_type: Literal["FILING_CHUNK", "STRUCTURED_FACT", "AUDIT_EVENT"] = "FILING_CHUNK"

class CitationsAppendix(BaseModel):
    sources: List[CitationSource] = Field(default_factory=list, description="All grounded sources used in generating the response")
