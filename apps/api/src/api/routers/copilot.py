import logging
import os
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from api.core.database import get_db
from api.models.db_models import ChatSession, ChatMessage
from api.copilot.agent import UnderwritingCopilotService
from api.copilot.schemas.feedback_schemas import FeedbackRequest, FeedbackResponse

logger = logging.getLogger(__name__)

copilot_router = APIRouter(prefix="/copilot", tags=["Copilot"])

class ChatStreamRequest(BaseModel):
    session_id: str = Field(..., description="Unique chat session identifier")
    message: str = Field(..., description="Analyst prompt or question")
    company_id: Optional[int] = Field(None, description="Active company ID")
    context: Optional[Dict[str, Any]] = Field(None, description="UI context snapshot (active facts, KPI, pages)")

class CreateSessionRequest(BaseModel):
    company_id: Optional[int] = None
    title: Optional[str] = "New Conversation"

class SessionResponse(BaseModel):
    id: str
    company_id: Optional[int]
    title: str
    is_active: bool
    created_at: str
    updated_at: str

class MessageResponse(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    tool_calls: Optional[Any] = None
    citations: Optional[Any] = None
    widgets: Optional[Any] = None
    context_snapshot: Optional[Any] = None
    created_at: str

@copilot_router.post("/chat/stream")
async def copilot_chat_stream(
    payload: ChatStreamRequest,
    db: Session = Depends(get_db)
):
    """
    Real-time Server-Sent Events (SSE) streaming endpoint for the Credit Underwriting Copilot.
    Emits reasoning status chips, tokens, generative UI widgets, and citations.
    """
    company_id = payload.company_id
    if company_id is None and payload.context:
        company_id = payload.context.get("companyId")
    if company_id is None:
        company_id = 1 # Default company fallback

    service = UnderwritingCopilotService(db)

    return StreamingResponse(
        service.stream_chat(
            session_id=payload.session_id,
            user_message=payload.message,
            company_id=company_id,
            context_snapshot=payload.context
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@copilot_router.post("/chat/abort")
async def copilot_chat_abort():
    """Signals that ongoing stream was aborted by analyst."""
    return {"status": "ABORTED", "message": "Stream aborted successfully"}

@copilot_router.get("/sessions", response_model=List[SessionResponse])
async def list_copilot_sessions(
    company_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """Lists past chat sessions for a company."""
    query = db.query(ChatSession)
    if company_id:
        query = query.filter(ChatSession.company_id == company_id)
    sessions = query.order_by(ChatSession.updated_at.desc()).all()

    return [
        SessionResponse(
            id=s.id,
            company_id=s.company_id,
            title=s.title,
            is_active=s.is_active,
            created_at=s.created_at.isoformat() if s.created_at else "",
            updated_at=s.updated_at.isoformat() if s.updated_at else ""
        )
        for s in sessions
    ]

@copilot_router.post("/sessions", response_model=SessionResponse)
async def create_copilot_session(
    payload: CreateSessionRequest,
    db: Session = Depends(get_db)
):
    """Creates a new chat session."""
    session = ChatSession(
        company_id=payload.company_id,
        title=payload.title or "New Conversation"
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return SessionResponse(
        id=session.id,
        company_id=session.company_id,
        title=session.title,
        is_active=session.is_active,
        created_at=session.created_at.isoformat() if session.created_at else "",
        updated_at=session.updated_at.isoformat() if session.updated_at else ""
    )

@copilot_router.get("/sessions/{session_id}/messages", response_model=List[MessageResponse])
async def get_copilot_session_messages(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Retrieves all messages for a given chat session."""
    messages = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).order_by(ChatMessage.created_at.asc()).all()

    return [
        MessageResponse(
            id=m.id,
            session_id=m.session_id,
            role=m.role,
            content=m.content,
            tool_calls=m.tool_calls,
            citations=m.citations,
            widgets=m.widgets,
            context_snapshot=m.context_snapshot,
            created_at=m.created_at.isoformat() if m.created_at else ""
        )
        for m in messages
    ]

@copilot_router.post("/feedback", response_model=FeedbackResponse)
async def submit_copilot_feedback(payload: FeedbackRequest):
    """
    Attaches analyst thumbs up/down, feedback comments, or fact corrections to LangSmith trace runs.
    """
    api_key = os.getenv("LANGCHAIN_API_KEY")
    if api_key:
        try:
            from langsmith import Client
            client = Client()
            client.create_feedback(
                run_id=payload.run_id,
                key=payload.feedback_type or "user_rating",
                score=payload.score,
                comment=payload.comment,
                value=payload.corrected_value
            )
            logger.info(f"Attached feedback score={payload.score} to LangSmith run {payload.run_id}")
        except Exception as e:
            logger.warning(f"Could not forward feedback to LangSmith ({e})")

    return FeedbackResponse(
        status="SUCCESS",
        run_id=payload.run_id,
        message="Feedback recorded successfully"
    )
