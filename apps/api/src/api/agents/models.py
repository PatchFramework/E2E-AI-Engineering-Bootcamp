from pydantic import BaseModel, Field
from typing import Annotated, List, Any
from operator import add

class RagUsedContext(BaseModel):
    id: str = Field(description="ID of the item used to answer the question")
    description: str = Field(description="Description of the item used to answer the question")

class FinalResponse(BaseModel):
    """Call this tool when the final answer to the user can be formulated."""
    answer: str = Field(description="Final answer to the question")
    citations: list[RagUsedContext] = Field(description="List of items that were relevant to create the final answer")

class State(BaseModel):
    messages: Annotated[List[Any], add] = []
    iteration: int = 0
    answer: str = ""
    final_answer: bool = False
    question_relevant: bool = False
    trace_id: str = ""
    citations: list = []


class IntentRouterResponse(BaseModel):
    question_relevant: bool
    answer: str = Field(description="A politely dismissive and humorous answer to the question if the users query is not relevant.")