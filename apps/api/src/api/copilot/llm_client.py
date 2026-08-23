import os
import logging
from functools import lru_cache
from typing import Optional, List, Dict, Any
from langchain_openai import ChatOpenAI

from api.copilot.token_tracker import extract_token_usage, merge_token_usages

logger = logging.getLogger(__name__)

DEFAULT_COPILOT_MODEL = "gpt-4o-mini"

def get_default_model_name() -> str:
    """Retrieves the globally configured Copilot LLM model name."""
    return os.getenv("COPILOT_LLM_MODEL") or os.getenv("OPENAI_MODEL") or DEFAULT_COPILOT_MODEL

def empty_token_usage() -> Dict[str, int]:
    """Returns an initialized zeroed token usage dictionary."""
    return {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "cached_tokens": 0,
        "reasoning_tokens": 0,
        "total_tokens": 0
    }

@lru_cache(maxsize=16)
def _get_cached_chat_openai(
    model_name: str,
    temperature: float,
    api_key: Optional[str]
) -> ChatOpenAI:
    """
    Internal LRU-cached factory maintaining persistent HTTP connection pools
    (keep-alive) to api.openai.com, avoiding repeated TCP/TLS handshake overhead.
    """
    return ChatOpenAI(
        model=model_name,
        temperature=temperature,
        api_key=api_key or os.getenv("OPENAI_API_KEY"),
        max_retries=2,
        request_timeout=60.0
    )

def get_chat_openai(
    model_name: Optional[str] = None,
    temperature: float = 0.0,
    tags: Optional[List[str]] = None,
    company_id: Optional[int] = None
) -> ChatOpenAI:
    """
    Returns a configured ChatOpenAI instance using persistent connection pooling.
    """
    model = model_name or get_default_model_name()
    api_key = os.getenv("OPENAI_API_KEY")
    return _get_cached_chat_openai(model, temperature, api_key)
