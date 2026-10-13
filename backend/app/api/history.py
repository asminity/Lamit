from fastapi import APIRouter, Depends, Request
from backend.app.core.database import get_db_pool
from backend.app.core.security import AuthenticatedUser, get_current_user, verify_thread_ownership
from backend.app.schemas.thread import ChatHistoryResponse, ChatMessageItem
from backend.app.graph.engine import checkpointer

router = APIRouter(prefix="/threads", tags=["history"])


@router.get("/{thread_id}/messages", response_model=ChatHistoryResponse)
async def get_thread_messages(
    thread_id: str,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    pool = await get_db_pool()
    async with pool.connection() as conn:
        await verify_thread_ownership(conn, thread_id, current_user.user_id)

        result = await conn.execute(
            """
            SELECT id, thread_id, role, content, tool_name, created_at
            FROM chat_messages
            WHERE thread_id = %s
            ORDER BY id ASC
            """,
            (thread_id,),
        )
        rows = await result.fetchall()

        if not rows and checkpointer is not None:
            try:
                cp = await checkpointer.aget_tuple({"configurable": {"thread_id": thread_id}})
                if cp:
                    cp_msgs = cp.checkpoint.get("channel_values", {}).get("messages", [])
                    for m in cp_msgs:
                        m_type = getattr(m, "type", "")
                        raw_content = getattr(m, "content", "")
                        if m_type in ("human", "ai") and raw_content:
                            text = raw_content if isinstance(raw_content, str) else str(raw_content)
                            if text.strip():
                                role = "user" if m_type == "human" else "assistant"
                                await conn.execute(
                                    "INSERT INTO chat_messages (thread_id, role, content) VALUES (%s, %s, %s)",
                                    (thread_id, role, text.strip()),
                                )
                    result = await conn.execute(
                        """
                        SELECT id, thread_id, role, content, tool_name, created_at
                        FROM chat_messages
                        WHERE thread_id = %s
                        ORDER BY id ASC
                        """,
                        (thread_id,),
                    )
                    rows = await result.fetchall()
            except Exception:
                pass

    messages = [ChatMessageItem(**row) for row in rows]
    return ChatHistoryResponse(thread_id=thread_id, messages=messages)
