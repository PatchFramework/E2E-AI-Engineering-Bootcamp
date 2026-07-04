from pydantic import BaseModel
from typing import Optional


class RAGRequest(BaseModel):
    query: str

class RagUsedContext(BaseModel):
    description: str
    img_url: Optional[str] = None
    product_url: str
    rating: Optional[float] = None
    rating_number: Optional[int] = None
    

class RAGResponse(BaseModel):
    answer: str
    citations: list[RagUsedContext]