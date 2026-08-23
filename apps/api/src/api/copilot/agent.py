import asyncio
import json
import logging
import uuid
import os
from datetime import datetime
from typing import AsyncGenerator, Dict, Any, Optional, List
from sqlalchemy.orm import Session
from langchain_core.messages import HumanMessage, AIMessage
from langsmith import traceable

from api.models.db_models import ChatSession, ChatMessage
from api.copilot.graph import build_copilot_graph
from api.copilot.state import CopilotGraphState
from api.copilot.pruning import prune_messages_state

logger = logging.getLogger(__name__)

class UnderwritingCopilotService:
    def __init__(self, db: Session):
        self.db = db
        self.graph = build_copilot_graph(db)

    @traceable(name="_fetch_or_create_chat_session_in_db")
    def _fetch_or_create_chat_session_in_db(self, session_id, company_id, user_message):
        chat_session = self.db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if not chat_session:
            chat_session = ChatSession(
                id=session_id,
                company_id=company_id,
                title=user_message[:32] + ("..." if len(user_message) > 32 else ""),
                created_at=datetime.utcnow()
            )
            self.db.add(chat_session)
            self.db.commit()

    @traceable(name="_persist_user_message")
    def _persist_user_message(self, session_id, user_message, context_snapshot):
        user_db_msg = ChatMessage(
            id=str(uuid.uuid4()),
            session_id=session_id,
            role="user",
            content=user_message,
            context_snapshot=context_snapshot,
            created_at=datetime.utcnow()
        )
        self.db.add(user_db_msg)
        self.db.commit()


    async def stream_chat(
        self,
        session_id: str,
        user_message: str,
        company_id: int,
        context_snapshot: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = "analyst"
    ) -> AsyncGenerator[str, None]:
        """
        Executes the LangGraph Copilot workflow and streams SSE frames to the client.
        Persists conversation state into PostgreSQL `chat_sessions` and `chat_messages`.
        """
        context_snapshot = context_snapshot or {}
        active_metric = context_snapshot.get("activeMetric")

        # 1. Fetch or create ChatSession in DB
        self._fetch_or_create_chat_session_in_db(session_id, company_id, user_message)
        

        # 2. Persist User Message
        self._persist_user_message(session_id, user_message, context_snapshot)

        # 3. Load historical messages from DB
        db_messages = self.db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.created_at.asc()).all()

        langchain_messages = []
        for m in db_messages:
            if m.role == "user":
                langchain_messages.append(HumanMessage(content=m.content))
            elif m.role == "assistant":
                langchain_messages.append(AIMessage(content=m.content))

        # Prune old tool messages and count turns
        pruned_messages = prune_messages_state(langchain_messages)
        turn_count = len([m for m in pruned_messages if isinstance(m, HumanMessage)])

        # Generate run ID and model configuration for LangSmith tracing
        run_id = str(uuid.uuid4())
        model_name = os.getenv("COPILOT_LLM_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4o"
        run_uuid = uuid.UUID(run_id)

        run_config = {
            "run_id": run_uuid,
            "run_name": "UnderwritingCopilot",
            "tags": ["underwriting-copilot", f"company-{company_id}", model_name],
            "metadata": {
                "session_id": session_id,
                "company_id": company_id,
                "user_id": user_id,
                "model": model_name,
                "ls_model_name": model_name,
                "ls_provider": "openai",
            }
        }

        # Initial State
        initial_state: CopilotGraphState = {
            "messages": pruned_messages,
            "clean_event_history": [],
            "company_id": company_id,
            "session_id": session_id,
            "user_id": user_id,
            "active_metric": active_metric,
            "context_snapshot": context_snapshot,
            "execution_plan": [],
            "completed_steps": [],
            "pending_parallel_tasks": [],
            "current_step_index": 0,
            "reasoning_status": "Analyzing request & underwriting context...",
            "metric_substate": None,
            "rag_substate": None,
            "audit_substate": None,
            "gen_ui_substate": None,
            "metric_results": None,
            "rag_chunks": None,
            "quality_issues": None,
            "pending_widget": None,
            "widget_validation_retries": 0,
            "widget_validation_error": None,
            "retrieved_sources": [],
            "run_id": run_id,
            "turn_count": turn_count,
            "model_used": model_name,
            "token_usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "cached_tokens": 0,
                "reasoning_tokens": 0,
                "total_tokens": 0
            }
        }

        # 4. Stream Initial Handshake & Status Events
        yield f"event: trace\ndata: {json.dumps({'run_id': run_id, 'model': model_name})}\n\n"
        yield f"event: status\ndata: {json.dumps({'step': 'plan', 'message': 'Analyzing request & underwriting context...'})}\n\n"

        try:
            # 5. Run Graph Workflow (sync execution wrapped in asyncio with LangSmith config)
            loop = asyncio.get_running_loop()
            final_state = await loop.run_in_executor(
                None,
                lambda: self.graph.invoke(initial_state, config=run_config)
            )

            # Emit intermediate status updates if any
            if final_state.get("reasoning_status"):
                yield f"event: status\ndata: {json.dumps({'step': 'process', 'message': final_state['reasoning_status']})}\n\n"

            # 6. Stream Assistant Content Tokens
            assistant_messages = [m for m in final_state.get("messages", []) if isinstance(m, AIMessage)]
            final_ai_msg = assistant_messages[-1] if assistant_messages else AIMessage(content="Analysis complete.")
            full_text = final_ai_msg.content

            # Token streaming simulation over SSE
            words = full_text.split(" ")
            for idx, word in enumerate(words):
                chunk = (word if idx == 0 else " " + word)
                yield f"data: {json.dumps({'content': chunk})}\n\n"
                await asyncio.sleep(0.015)

            # 7. Stream Validated Generative UI Widget (if generated)
            final_widget = final_state.get("pending_widget")
            if final_widget:
                yield f"event: widget\ndata: {json.dumps(final_widget)}\n\n"
                yield f"data: {json.dumps({'widget': final_widget})}\n\n"

            # 8. Stream Grounded Citations Array
            citations_list = [c.model_dump() for c in final_state.get("retrieved_sources", [])]
            if citations_list:
                # Format to camelCase for frontend CopilotCitation model
                frontend_citations = [
                    {
                        "documentId": c["document_id"],
                        "filename": c["filename"],
                        "pageNumber": c["page_number"],
                        "displayedPage": c["displayed_page"],
                        "section": c.get("section"),
                        "snippet": c.get("snippet"),
                        "boundingBox": c.get("bounding_box")
                    }
                    for c in citations_list
                ]
                yield f"event: citations\ndata: {json.dumps(frontend_citations)}\n\n"
                yield f"data: {json.dumps({'citations': frontend_citations})}\n\n"

            # 9. Extract total tokens consumed and persist Assistant Response in PostgreSQL
            final_token_usage = final_state.get("token_usage") or {
                "prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0, "reasoning_tokens": 0, "total_tokens": 0
            }
            assistant_db_msg = ChatMessage(
                id=str(uuid.uuid4()),
                session_id=session_id,
                role="assistant",
                content=full_text,
                tool_calls={
                    "run_id": run_id,
                    "model": model_name,
                    "token_usage": final_token_usage
                },
                widgets=[final_widget] if final_widget else None,
                citations=citations_list if citations_list else None,
                created_at=datetime.utcnow()
            )
            self.db.add(assistant_db_msg)
            self.db.commit()

            # 10. Done Event with token accounting metadata
            yield f"event: done\ndata: {json.dumps({'session_id': session_id, 'message_id': assistant_db_msg.id, 'turn_count': turn_count, 'max_turns': 10, 'model': model_name, 'token_usage': final_token_usage})}\n\n"
            yield f"data: [DONE]\n\n"

        except asyncio.CancelledError:
            logger.info(f"Stream generation cancelled by client for session {session_id}")
            raise
        except Exception as e:
            logger.exception(f"Copilot streaming workflow failed: {e}")
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
