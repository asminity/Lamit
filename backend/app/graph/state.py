from langgraph.graph import MessagesState


class ChatState(MessagesState):
    """
    LangGraph execution state.
    Inherits 'messages' from MessagesState with append reducer.
    Extends with 'summary' for compressed conversational history.
    """
    summary: str
