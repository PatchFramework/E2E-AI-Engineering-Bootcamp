from pydantic import BaseModel
from typing import Optional


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