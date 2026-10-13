from langgraph.graph import END
from langgraph.prebuilt import tools_condition

from backend.app.core.config import settings
from backend.app.graph.state import ChatState


def summary_condition(state: ChatState) -> bool:
    """Returns True if message count exceeds summary trigger limit."""
    return len(state.get("messages", [])) > settings.SUMMARY_TRIGGER


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
