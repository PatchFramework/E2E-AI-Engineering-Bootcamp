from typing import List
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage

MAX_CONVERSATION_TURNS = 10
TOOL_RETENTION_TURNS = 3

def prune_messages_state(messages: List[BaseMessage]) -> List[BaseMessage]:
    """
    Prunes intermediate ToolMessages older than `TOOL_RETENTION_TURNS` to prevent
    context window bloat, while preserving user prompts and assistant syntheses.
    """
    if not messages:
        return messages

    # Count user messages to determine conversation turns
    user_indices = [i for i, m in enumerate(messages) if isinstance(m, HumanMessage)]
    total_turns = len(user_indices)

    if total_turns <= TOOL_RETENTION_TURNS:
        return messages

    # The cutoff index is the start of the (total_turns - TOOL_RETENTION_TURNS)-th turn
    cutoff_turn_idx = total_turns - TOOL_RETENTION_TURNS
    cutoff_msg_idx = user_indices[cutoff_turn_idx]

    pruned: List[BaseMessage] = []
    for idx, msg in enumerate(messages):
        if idx < cutoff_msg_idx:
            # For older turns, keep HumanMessages and AIMessages that have text content,
            # but drop raw ToolMessages and AIMessages that only contained tool_calls without text.
            if isinstance(msg, HumanMessage):
                pruned.append(msg)
            elif isinstance(msg, AIMessage) and msg.content:
                # Remove raw tool_calls array from older assistant messages if present
                clean_ai_msg = AIMessage(content=msg.content)
                pruned.append(clean_ai_msg)
        else:
            # For recent turns, keep all messages including tool calls and outputs
            pruned.append(msg)

    return pruned

def is_turn_limit_reached(turn_count: int) -> bool:
    """Returns True if the conversation has reached or exceeded the 10-turn cap."""
    return turn_count >= MAX_CONVERSATION_TURNS

TURN_LIMIT_WARNING = (
    "\n\n> ⚠️ **Conversation Limit Reached (10/10 turns):** "
    "To maintain reasoning precision and prevent context degradation, "
    "please start a new chat session using the **[+ New Chat]** button."
)
