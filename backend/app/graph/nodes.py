from langchain_core.messages import SystemMessage, HumanMessage, RemoveMessage
from langchain_openai import ChatOpenAI

from backend.app.core.config import settings
from backend.app.graph.state import ChatState
from backend.app.graph.tools.registry import tools

# LLM bound with tools
chat_llm = ChatOpenAI(
    model=settings.MODEL_NAME,
    temperature=0,
).bind_tools(tools)

# LLM for conversation summarization (unbound)
summary_llm = ChatOpenAI(
    model=settings.MODEL_NAME,
)


async def chat_node(state: ChatState):
    """
    Primary chat node: feeds summary context + working messages into LLM.
    """
    messages = []
    if state.get("summary"):
        messages.append(
            SystemMessage(content=f"Conversational History: {state['summary']}")
        )
    messages.extend(state["messages"])
    response = await chat_llm.ainvoke(messages)
    return {"messages": [response]}


async def summarize_node(state: ChatState):
    """
    Compresses older turns when message threshold is reached.
    Emits RemoveMessage objects to truncate working context while preserving the last turn.
    """
    existing_summary = state.get("summary", "")

    human_indices = [i for i, m in enumerate(state["messages"]) if isinstance(m, HumanMessage)]
    split_idx = human_indices[-1] if human_indices else -2
    messages_to_summarize = state["messages"][:split_idx]

    if not messages_to_summarize:
        return {}

    if existing_summary:
        prompt = f"""
Based on the given existing summary below, extend the summary by creating a precise summary of the existing summary and current conversation.

existing_summary = {existing_summary}
messages = {messages_to_summarize}
"""
    else:
        prompt = f"""
Create a precise summary of the given conversation.
messages = {messages_to_summarize}
"""

    response = await summary_llm.ainvoke(prompt)

    return {
        "summary": response.content,
        "messages": [RemoveMessage(id=m.id) for m in messages_to_summarize if getattr(m, "id", None)],
    }
