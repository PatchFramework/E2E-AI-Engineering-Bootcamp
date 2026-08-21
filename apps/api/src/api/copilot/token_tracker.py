from typing import Dict, Any, Optional
from langchain_core.messages import AIMessage

def extract_token_usage(ai_msg: Optional[AIMessage]) -> Dict[str, int]:
    """
    Extracts structured token breakdown (prompt_tokens, completion_tokens, cached_tokens, reasoning_tokens, total_tokens)
    from an AIMessage's usage_metadata or response_metadata.
    """
    usage = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "cached_tokens": 0,
        "reasoning_tokens": 0,
        "total_tokens": 0,
    }
    if not ai_msg:
        return usage

    # 1. Primary: LangChain standard usage_metadata
    um = getattr(ai_msg, "usage_metadata", None) or {}
    if um:
        usage["prompt_tokens"] = int(um.get("input_tokens", 0))
        usage["completion_tokens"] = int(um.get("output_tokens", 0))
        usage["total_tokens"] = int(um.get("total_tokens", usage["prompt_tokens"] + usage["completion_tokens"]))
        
        input_details = um.get("input_token_details", {}) or {}
        output_details = um.get("output_token_details", {}) or {}
        usage["cached_tokens"] = int(input_details.get("cache_read", 0))
        usage["reasoning_tokens"] = int(output_details.get("reasoning", 0))
        return usage

    # 2. Secondary: OpenAI response_metadata['token_usage']
    rm = getattr(ai_msg, "response_metadata", None) or {}
    tu = rm.get("token_usage", {}) or {}
    if tu:
        usage["prompt_tokens"] = int(tu.get("prompt_tokens", 0))
        usage["completion_tokens"] = int(tu.get("completion_tokens", 0))
        usage["total_tokens"] = int(tu.get("total_tokens", usage["prompt_tokens"] + usage["completion_tokens"]))
        
        pt_details = tu.get("prompt_tokens_details", {}) or {}
        ct_details = tu.get("completion_tokens_details", {}) or {}
        usage["cached_tokens"] = int(pt_details.get("cached_tokens", 0))
        usage["reasoning_tokens"] = int(ct_details.get("reasoning_tokens", 0))

    return usage

def merge_token_usages(usage_a: Optional[Dict[str, int]], usage_b: Optional[Dict[str, int]]) -> Dict[str, int]:
    """Merges two token consumption records."""
    a = usage_a or {}
    b = usage_b or {}
    return {
        "prompt_tokens": int(a.get("prompt_tokens", 0)) + int(b.get("prompt_tokens", 0)),
        "completion_tokens": int(a.get("completion_tokens", 0)) + int(b.get("completion_tokens", 0)),
        "cached_tokens": int(a.get("cached_tokens", 0)) + int(b.get("cached_tokens", 0)),
        "reasoning_tokens": int(a.get("reasoning_tokens", 0)) + int(b.get("reasoning_tokens", 0)),
        "total_tokens": int(a.get("total_tokens", 0)) + int(b.get("total_tokens", 0)),
    }

def format_langsmith_token_metadata(model_name: str, token_usage: Dict[str, int]) -> Dict[str, Any]:
    """
    Constructs standardized LangSmith cost tracking and token metadata dictionary.
    """
    return {
        "ls_model_name": model_name,
        "ls_provider": "openai",
        "ls_model_type": "chat",
        "model": model_name,
        "usage_metadata": {
            "input_tokens": token_usage.get("prompt_tokens", 0),
            "output_tokens": token_usage.get("completion_tokens", 0),
            "total_tokens": token_usage.get("total_tokens", 0),
            "input_token_details": {
                "cache_read": token_usage.get("cached_tokens", 0)
            },
            "output_token_details": {
                "reasoning": token_usage.get("reasoning_tokens", 0)
            }
        },
        "token_usage": token_usage
    }
