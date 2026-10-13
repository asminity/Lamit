import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from backend.app.core.database import get_db_pool
from backend.app.core.security import AuthenticatedUser, get_current_user, verify_thread_ownership
from backend.app.schemas.thread import ThreadCreateResponse, ThreadItem, ThreadTitleUpdate

router = APIRouter(prefix="/threads", tags=["threads"])


def generate_thread_id() -> str:
    if hasattr(uuid, "uuid7"):
        return str(uuid.uuid7())
    return str(uuid.uuid4())


@router.get("", response_model=List[ThreadItem])
async def list_threads(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    pool = await get_db_pool()
    async with pool.connection() as conn:
        result = await conn.execute(
            """
            SELECT thread_id, title, created_at, updated_at
            FROM chat_threads
            WHERE user_id = %s
            ORDER BY updated_at DESC
            """,
            (current_user.user_id,),
        )
        rows = await result.fetchall()
    return [ThreadItem(**row) for row in rows]


@router.post("", response_model=ThreadCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_thread(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    thread_id = generate_thread_id()
    pool = await get_db_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO chat_threads (thread_id, user_id, title)
            VALUES (%s, %s, %s)
            """,
            (thread_id, current_user.user_id, "New Conversation"),
        )
    return ThreadCreateResponse(thread_id=thread_id)


@router.delete("/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_thread(
    thread_id: str,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    pool = await get_db_pool()
    async with pool.connection() as conn:
        await verify_thread_ownership(conn, thread_id, current_user.user_id)

        await conn.execute("DELETE FROM chat_messages WHERE thread_id = %s", (thread_id,))
        await conn.execute("DELETE FROM chat_threads WHERE thread_id = %s", (thread_id,))

        try:
            await conn.execute("DELETE FROM checkpoint_writes WHERE thread_id = %s", (thread_id,))
            await conn.execute("DELETE FROM checkpoints WHERE thread_id = %s", (thread_id,))
            await conn.execute("DELETE FROM checkpoint_blobs WHERE thread_id = %s", (thread_id,))
        except Exception:
            pass

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{thread_id}/title")
async def update_thread_title(
    thread_id: str,
    body: ThreadTitleUpdate,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    pool = await get_db_pool()
    async with pool.connection() as conn:
        await verify_thread_ownership(conn, thread_id, current_user.user_id)

        result = await conn.execute(
            """
            UPDATE chat_threads
            SET title = %s, updated_at = CURRENT_TIMESTAMP
            WHERE thread_id = %s AND user_id = %s
            RETURNING thread_id, title
            """,
            (body.title, thread_id, current_user.user_id),
        )
        row = await result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Thread not found")

    return {"thread_id": row["thread_id"], "title": row["title"]}
