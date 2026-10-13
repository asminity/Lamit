import logging
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

from backend.app.core.config import settings

logger = logging.getLogger("title_service")

llm = ChatOpenAI(
    model=settings.MODEL_NAME,
)

SYSTEM_PROMPT = SystemMessage(
    content=(
        "You are an assistant that summarizes conversations into concise, meaningful titles. "
        "Generate a title in 3 to 5 words. "
        "Output ONLY the title itself. Do not include quotes, markdown formatting, or ending punctuation."
    )
)


def _format_dialogue_snippet(messages: list) -> str:
    dialogue_lines = []
    for msg in messages[:4]:
        if isinstance(msg, dict):
            role = msg.get("role", "User").capitalize()
            content = msg.get("content", "").strip()
        else:
            role = getattr(msg, "type", "User").capitalize()
            content = getattr(msg, "content", "").strip()
        if content:
            dialogue_lines.append(f"{role}: {content}")
    return "\n".join(dialogue_lines)


def generate_title_with_ai(messages: list, thread_id: str = None) -> str:
    """Synchronously generate a concise title using AI."""
    if not messages:
        return "New Conversation"

    conversation_text = _format_dialogue_snippet(messages)
    if not conversation_text:
        return "New Conversation"

    user_prompt = HumanMessage(content=f"Conversation snippet:\n{conversation_text}\n\nTitle:")
    config = {
        "run_name": "generate_title",
        "tags": ["title_generation"],
    }
    if thread_id:
        config["metadata"] = {"thread_id": thread_id}
        config["configurable"] = {"thread_id": thread_id}

    try:
        response = llm.invoke([SYSTEM_PROMPT, user_prompt], config=config)
        title = response.content.strip().strip("\"'")
        return title if title else "New Conversation"
    except Exception as e:
        logger.warning(f"Fallback title generation due to: {e}")
        first_content = messages[0].get("content", "") if isinstance(messages[0], dict) else getattr(messages[0], "content", "")
        return (first_content[:25] + "...") if first_content else "New Conversation"


async def async_generate_title_with_ai(messages: list, thread_id: str = None) -> str:
    """Asynchronously generate a concise title using AI."""
    if not messages:
        return "New Conversation"

    conversation_text = _format_dialogue_snippet(messages)
    if not conversation_text:
        return "New Conversation"

    user_prompt = HumanMessage(content=f"Conversation snippet:\n{conversation_text}\n\nTitle:")
    config = {
        "run_name": "generate_title",
        "tags": ["title_generation"],
    }
    if thread_id:
        config["metadata"] = {"thread_id": thread_id}
        config["configurable"] = {"thread_id": thread_id}

    try:
        response = await llm.ainvoke([SYSTEM_PROMPT, user_prompt], config=config)
        title = response.content.strip().strip("\"'")
        return title if title else "New Conversation"
    except Exception as e:
        logger.warning(f"Fallback async title generation due to: {e}")
        first_content = messages[0].get("content", "") if isinstance(messages[0], dict) else getattr(messages[0], "content", "")
        return (first_content[:25] + "...") if first_content else "New Conversation"
