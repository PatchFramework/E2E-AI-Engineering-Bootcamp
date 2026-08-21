from typing import Optional, Literal
from pydantic import BaseModel, Field

class FeedbackRequest(BaseModel):
    run_id: str = Field(..., description="LangSmith root run UUID or execution trace ID")
    score: Literal[1, 0, -1] = Field(..., description="1 for thumbs up, -1 for thumbs down, 0 for neutral")
    feedback_type: Optional[str] = Field("user_rating", description="Category: 'user_rating', 'fact_correction', etc.")
    comment: Optional[str] = Field(None, description="Optional text feedback from analyst")
    corrected_value: Optional[str] = Field(None, description="If reporting fact discrepancy, the corrected value")

class FeedbackResponse(BaseModel):
    status: str
    run_id: str
    message: str
