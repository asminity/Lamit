from typing import Optional, Dict, Any
from langgraph.graph import MessagesState


class ChatState(MessagesState):
    """
    LangGraph execution state.
    Inherits 'messages' from MessagesState with append reducer.
    Extends with:
    - summary: compressed rolling conversational history
    - active_task: structured tracking of current goals, steps, constraints, and artifacts
    - memory_context: relevant retrieved long-term memories injected for prompt augmentation
    - user_id: tenant user ID for security and memory isolation
    """
    summary: Optional[str]
    active_task: Optional[Dict[str, Any]]
    memory_context: Optional[str]
    user_id: Optional[str]

