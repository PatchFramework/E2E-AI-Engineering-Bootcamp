from api.api.models import AgentUsedContext
from api.agents.graph import rag_agent_wrapper
from fastapi import APIRouter, Request
from api.api.models import AgentRequest, AgentResponse
from api.agents.retrieval_generation import rag_pipeline
from qdrant_client import QdrantClient
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

rag_router = APIRouter()

@rag_router.post("/")
def chat(
    request: Request,
    payload: AgentRequest
) -> AgentResponse:

    result = rag_agent_wrapper(payload.query, payload.thread_id)

    return AgentResponse(
        answer=result["answer"], 
        citations=[AgentUsedContext(**context) for context in result["used_context"]])


api_router = APIRouter()
api_router.include_router(rag_router, prefix="/agent", tags=["agent"])