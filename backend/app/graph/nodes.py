from langchain_core.messages import SystemMessage, HumanMessage, RemoveMessage
from langchain_openai import ChatOpenAI

from backend.app.core.config import settings
from backend.app.graph.state import ChatState
from backend.app.graph.tools.registry import tools
from backend.app.graph.tokens import partition_messages_for_summary

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
    Primary chat node: feeds memory context + active task + rolling summary + working messages into LLM.
    """
    system_sections = []

    if state.get("memory_context"):
        system_sections.append(
            f"### Long-Term Memory & User Profile Context:\n{state['memory_context']}"
        )

    if state.get("active_task"):
        task = state["active_task"]
        if isinstance(task, dict):
            task_lines = [f"- **{k.replace('_', ' ').capitalize()}**: {v}" for k, v in task.items()]
            system_sections.append(f"### Current Active Task State:\n" + "\n".join(task_lines))
        elif isinstance(task, str) and task.strip():
            system_sections.append(f"### Current Active Task State:\n{task}")

    if state.get("summary"):
        system_sections.append(
            f"### Compressed Previous Conversation Summary:\n{state['summary']}"
        )

    messages = []
    if system_sections:
        messages.append(SystemMessage(content="\n\n".join(system_sections)))
    messages.extend(state["messages"])

    response = await chat_llm.ainvoke(messages)
    return {"messages": [response]}


async def summarize_node(state: ChatState):
    """
    Compresses older turns when token or message threshold is reached.
    Safely partitions messages to preserve tool-call/tool-result consistency.
    Emits RemoveMessage objects to truncate working context while preserving recent complete turns.
    """
    existing_summary = state.get("summary", "")
    working_messages = state.get("messages", [])

    messages_to_summarize, remaining_messages = partition_messages_for_summary(
        working_messages,
        recent_token_budget=settings.STM_RECENT_MESSAGES_TOKEN_LIMIT,
        min_recent_turns=1,
        model_name=settings.MODEL_NAME,
    )

    if not messages_to_summarize:
        return {}

    formatted_msgs = []
    for m in messages_to_summarize:
        role = getattr(m, "type", m.__class__.__name__)
        content = getattr(m, "content", "")
        if isinstance(content, str) and content.strip():
            formatted_msgs.append(f"{role}: {content}")
        elif getattr(m, "tool_calls", None):
            formatted_msgs.append(f"assistant (tool_calls): {m.tool_calls}")

    conversation_text = "\n".join(formatted_msgs)

    if existing_summary:
        prompt = f"""You are a conversation summarizer maintaining a rolling concise memory.
Extend the existing summary by incorporating the older conversation turns below.
Capture key facts, user preferences, tasks discussed, and tool outcomes. Keep it dense and informative.

Existing Summary:
{existing_summary}

Older Conversation to Incorporate:
{conversation_text}

Produce an updated, cohesive summary:"""
    else:
        prompt = f"""You are a conversation summarizer maintaining a rolling concise memory.
Create a precise, structured summary of the conversation turns below.
Capture key facts, user preferences, tasks discussed, and tool outcomes. Keep it dense and informative.

Conversation:
{conversation_text}

Produce a cohesive summary:"""

    response = await summary_llm.ainvoke(prompt)
    summary_text = response.content if isinstance(response.content, str) else str(response.content)

    remove_ops = [
        RemoveMessage(id=m.id) for m in messages_to_summarize if getattr(m, "id", None)
    ]

    return {
        "summary": summary_text.strip(),
        "messages": remove_ops,
    }

