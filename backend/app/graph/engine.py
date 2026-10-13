import logging
from typing import Optional
from psycopg_pool import AsyncConnectionPool
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.prebuilt import ToolNode

from backend.app.core.database import pool, setup_database_tables
from backend.app.graph.state import ChatState
from backend.app.graph.nodes import chat_node, summarize_node
from backend.app.graph.routing import route_after_chat
from backend.app.graph.tools.registry import tools

logger = logging.getLogger("graph_engine")

# Construct StateGraph
graph_builder = StateGraph(ChatState)
graph_builder.add_node("chat_node", chat_node)
graph_builder.add_node("tools", ToolNode(tools, handle_tool_errors=True))
graph_builder.add_node("summarize", summarize_node)

graph_builder.add_edge(START, "chat_node")
graph_builder.add_conditional_edges(
    "chat_node",
    route_after_chat,
    {
        "tools": "tools",
        "summarize": "summarize",
        END: END,
    },
)
graph_builder.add_edge("tools", "chat_node")
graph_builder.add_edge("summarize", END)

# Compiled graph and checkpointer
checkpointer: Optional[AsyncPostgresSaver] = None
chatbot = None


async def ensure_initialized(custom_pool: Optional[AsyncConnectionPool] = None):
    """
    Initializes database pool, checkpointer tables, database schemas, and compiles graph.
    Idempotent and thread-safe.
    """
    global checkpointer, chatbot
    active_pool = custom_pool or pool

    if active_pool.closed:
        await active_pool.open()

    if checkpointer is None:
        checkpointer = AsyncPostgresSaver(active_pool)
        await checkpointer.setup()
        chatbot = graph_builder.compile(checkpointer=checkpointer)
        logger.info("LangGraph compiled successfully with AsyncPostgresSaver.")

    await setup_database_tables()
    return chatbot


async def get_chatbot():
    """Returns initialized compiled LangGraph."""
    if chatbot is None:
        return await ensure_initialized()
    return chatbot
