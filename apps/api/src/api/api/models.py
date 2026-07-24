from pydantic import Field
from pydantic import BaseModel
from typing import Optional, Union


class AgentRequest(BaseModel):
    query: str
    thread_id: str

class AgentUsedContext(BaseModel):
    description: str
    img_url: Optional[str] = None
    product_url: str
    rating: Optional[float] = None
    rating_number: Optional[int] = None
    

class AgentResponse(BaseModel):
    answer: str
    citations: list[AgentUsedContext]
    trace_id: str


class FeedbackRequest(BaseModel):
    trace_id: str
    feedback_score: Union[int, None] = Field(description="Feedback score , 0 or 1")
    feedback_text: str = Field(description="Feedback text")
    feedback_source_type: str = Field(description="Feedback source type, 'api' or 'model'")


class FeedbackResponse(BaseModel):
    message: str = Field(description="Feedback submission message")