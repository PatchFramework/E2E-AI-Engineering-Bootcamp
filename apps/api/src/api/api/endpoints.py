from api.api.models import *
from api.agents.graph import rag_agent_wrapper
from fastapi import APIRouter, Request
from api.api.models import AgentRequest, AgentResponse
from api.agents.retrieval_generation import rag_pipeline
from qdrant_client import QdrantClient
import logging
from api.api.processors.submit_feedback import submit_feedback

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

rag_router = APIRouter()
feedback_router = APIRouter()

@rag_router.post("/")
def chat(
    request: Request,
    payload: AgentRequest
) -> AgentResponse:

    result = rag_agent_wrapper(payload.query, str(payload.thread_id))

    return AgentResponse(
        answer=result["answer"], 
        citations=[AgentUsedContext(**context) for context in result["used_context"]],
        trace_id=result["trace_id"]
        )

@feedback_router.post("/")
def send_feedback(
    request: Request,
    payload: FeedbackRequest
) -> FeedbackResponse:

    submit_feedback(
        trace_id=str(payload.trace_id),
        feedback_score=payload.feedback_score,
        feedback_text=payload.feedback_text,
        feedback_source_type=payload.feedback_source_type
    )

    return FeedbackResponse(
        message="Thanks for your feedback!"
    )

api_router = APIRouter()
api_router.include_router(rag_router, prefix="/agent", tags=["agent"])
api_router.include_router(feedback_router, prefix="/feedback", tags=["feedback"])