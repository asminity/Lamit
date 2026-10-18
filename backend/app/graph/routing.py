from langgraph.graph import END
from langgraph.prebuilt import tools_condition

from backend.app.core.config import settings
from backend.app.graph.state import ChatState
from backend.app.graph.tokens import count_messages_tokens


def summary_condition(state: ChatState) -> bool:
    """
    Returns True if:
    1. Working messages exceed the configured token threshold, OR
    2. Working message count exceeds the message count fallback limit.
    """
    messages = state.get("messages", [])
    if not messages:
        return False

    total_tokens = count_messages_tokens(messages, model_name=settings.MODEL_NAME)
    if total_tokens > settings.STM_SUMMARY_TRIGGER_TOKENS:
        return True

    return len(messages) > settings.SUMMARY_TRIGGER



def route_after_chat(state: ChatState):
    """
    Determines next step after LLM execution:
    1. If tool calls requested -> 'tools'
    2. Else if messages exceed threshold -> 'summarize'
    3. Else -> END
    """
    if tools_condition(state) == "tools":
        return "tools"
    if summary_condition(state):
        return "summarize"
    return END
