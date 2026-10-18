import asyncio
import json
import logging
from typing import AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.types import Command

from backend.app.core.config import settings
from backend.app.core.database import get_db_pool
from backend.app.core.security import AuthenticatedUser, get_current_user, verify_thread_ownership
from backend.app.schemas.chat import ChatStreamRequest, ChatResumeRequest
from backend.app.schemas.cache import CacheEntryCreate
from backend.app.services.title_service import async_generate_title_with_ai
from backend.app.services.semantic_cache import semantic_cache
from backend.app.services.memory_service import memory_service
from backend.app.graph.engine import get_chatbot



router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger("chat_stream")

_active_threads: set[str] = set()
_threads_lock = asyncio.Lock()


async def acquire_thread(thread_id: str) -> bool:
    async with _threads_lock:
        if thread_id in _active_threads:
            return False
        _active_threads.add(thread_id)
        return True


async def release_thread(thread_id: str):
    async with _threads_lock:
        _active_threads.discard(thread_id)


async def _generate_and_save_title(pool, thread_id: str):
    try:
        async with pool.connection() as conn:
            res = await conn.execute(
                """
                SELECT role, content
                FROM chat_messages
                WHERE thread_id = %s
                ORDER BY id ASC
                LIMIT 6
                """,
                (thread_id,),
            )
            rows = await res.fetchall()
            if not rows:
                return

            messages = [{"role": r["role"], "content": r["content"]} for r in rows]
            title = await async_generate_title_with_ai(messages, thread_id=thread_id)
            if title and title != "New Conversation":
                await conn.execute(
                    """
                    UPDATE chat_threads
                    SET title = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE thread_id = %s
                    """,
                    (title, thread_id),
                )
    except Exception:
        pass


@router.post("/stream")
async def chat_stream(
    body: ChatStreamRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    pool = await get_db_pool()
    bot = await get_chatbot()

    # 1. Verify thread ownership
    async with pool.connection() as conn:
        thread = await verify_thread_ownership(conn, body.thread_id, current_user.user_id)
        current_title = thread.get("title", "New Conversation")

    # 2. Concurrency lock
    if not await acquire_thread(body.thread_id):
        raise HTTPException(
            status_code=409,
            detail="A request is already actively processing for this thread. Please wait for it to complete.",
        )

    # 3. Persist user message
    async with pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO chat_messages (thread_id, role, content)
            VALUES (%s, 'user', %s)
            """,
            (body.thread_id, body.message.strip()),
        )
        await conn.execute(
            """
            UPDATE chat_threads SET updated_at = CURRENT_TIMESTAMP WHERE thread_id = %s
            """,
            (body.thread_id,),
        )

    # 4. Semantic cache lookup
    cache_result = None
    if settings.SEMANTIC_CACHE_ENABLED:
        try:
            cache_result = await semantic_cache.lookup(
                query=body.message.strip(),
                user_id=current_user.user_id,
                model_name=settings.MODEL_NAME,
            )
        except Exception:
            cache_result = None

    config = {
        "configurable": {"thread_id": body.thread_id},
        "metadata": {"thread_id": body.thread_id, "user_id": current_user.user_id},
        "run_name": "chat_turn",
        "tags": ["fastapi", "sse_stream"],
    }

    async def event_generator() -> AsyncGenerator[str, None]:
        full_assistant_reply = []
        last_tool_name = None
        assistant_persisted = False
        is_interrupted = False
        used_tools = []

        try:
            # Fast Path: Semantic Cache Hit
            if cache_result and cache_result.hit and cache_result.cached_response:
                cached_text = cache_result.cached_response
                # Stream cached text smoothly
                chunk_size = 24
                for i in range(0, len(cached_text), chunk_size):
                    chunk = cached_text[i : i + chunk_size]
                    yield f"event: text\ndata: {json.dumps({'content': chunk})}\n\n"
                    await asyncio.sleep(0.01)

                # Persist turn in chat_messages
                async with pool.connection() as conn:
                    await conn.execute(
                        """
                        INSERT INTO chat_messages (thread_id, role, content, tool_name)
                        VALUES (%s, 'assistant', %s, 'semantic_cache')
                        """,
                        (body.thread_id, cached_text),
                    )
                    await conn.execute(
                        "UPDATE chat_threads SET updated_at = CURRENT_TIMESTAMP WHERE thread_id = %s",
                        (body.thread_id,),
                    )

                # Synchronize LangGraph state so conversation context remains intact
                try:
                    await bot.aupdate_state(
                        config,
                        {
                            "messages": [
                                HumanMessage(content=body.message.strip()),
                                AIMessage(content=cached_text),
                            ]
                        },
                    )
                except Exception:
                    pass

                # Background AI title generation if needed
                title_updated = False
                if current_title in ("New Conversation", "New Chat", ""):
                    asyncio.create_task(_generate_and_save_title(pool, body.thread_id))
                    title_updated = True

                yield f"event: done\ndata: {json.dumps({'thread_id': body.thread_id, 'title_updated': title_updated, 'interrupted': False, 'cached': True, 'similarity': cache_result.similarity_score})}\n\n"
                return

            # Retrieve Long-Term Memory (LTM) context for prompt augmentation
            memory_context = ""
            if settings.LTM_ENABLED:
                try:
                    retrieved_memories = await memory_service.retrieve_memories(
                        user_id=current_user.user_id,
                        query=body.message.strip(),
                    )
                    if retrieved_memories:
                        memory_context = memory_service.format_memories_for_prompt(retrieved_memories)
                except Exception as e:
                    logger.warning(f"Error retrieving memories for user {current_user.user_id}: {e}")

            # Cache Miss: Execute LangGraph pipeline
            input_state = {
                "messages": [HumanMessage(content=body.message.strip())],
                "memory_context": memory_context,
                "user_id": current_user.user_id,
            }

            async for event in bot.astream_events(
                input_state,
                config=config,
                version="v2",
            ):
                if await request.is_disconnected():
                    break

                ev_type = event.get("event")

                if ev_type == "on_chat_model_stream":
                    chunk = event.get("data", {})["chunk"]
                    content = getattr(chunk, "content", None)
                    if isinstance(content, str) and content:
                        full_assistant_reply.append(content)
                        yield f"event: text\ndata: {json.dumps({'content': content})}\n\n"

                elif ev_type == "on_tool_start":
                    tool_name = event.get("name")
                    last_tool_name = tool_name
                    if tool_name:
                        used_tools.append(tool_name)
                    yield f"event: tool_start\ndata: {json.dumps({'name': tool_name})}\n\n"

                elif ev_type == "on_tool_end":
                    tool_name = event.get("name") or last_tool_name
                    yield f"event: tool_end\ndata: {json.dumps({'name': tool_name})}\n\n"

            # Check for HITL interrupt state
            state = await bot.aget_state(config)
            if state.next and state.tasks:
                for task in state.tasks:
                    if getattr(task, "interrupts", ()):
                        is_interrupted = True
                        interrupt_val = task.interrupts[0].value
                        yield f"event: interrupt\ndata: {json.dumps({'thread_id': body.thread_id, 'interrupt': interrupt_val})}\n\n"
                        break

            # Persist assistant turn if completed
            if full_assistant_reply and not assistant_persisted and not is_interrupted:
                final_text = "".join(full_assistant_reply).strip()
                if final_text:
                    async with pool.connection() as conn:
                        await conn.execute(
                            """
                            INSERT INTO chat_messages (thread_id, role, content, tool_name)
                            VALUES (%s, 'assistant', %s, %s)
                            """,
                            (body.thread_id, final_text, last_tool_name),
                        )
                        await conn.execute(
                            "UPDATE chat_threads SET updated_at = CURRENT_TIMESTAMP WHERE thread_id = %s",
                            (body.thread_id,),
                        )
                    assistant_persisted = True

                    # Trigger asynchronous non-blocking LTM extraction
                    if settings.LTM_ENABLED:
                        asyncio.create_task(
                            memory_service.extract_and_store_memories_async(
                                user_id=current_user.user_id,
                                thread_id=body.thread_id,
                                user_message=body.message.strip(),
                                assistant_message=final_text,
                            )
                        )

                    # Check eligibility and save to semantic cache asynchronously
                    if semantic_cache.is_response_cacheable(
                        tool_names=used_tools,
                        is_interrupted=is_interrupted,
                        response_text=final_text,
                    ):
                        async def _save_cache_entry():
                            try:
                                emb = await semantic_cache.get_embedding(body.message.strip())
                                if emb:
                                    await semantic_cache.store(
                                        CacheEntryCreate(
                                            user_id=current_user.user_id,
                                            query_text=body.message.strip(),
                                            response_text=final_text,
                                            embedding=emb,
                                            model_name=settings.MODEL_NAME,
                                            embedding_model=settings.SEMANTIC_CACHE_EMBEDDING_MODEL,
                                            config_version=settings.SEMANTIC_CACHE_CONFIG_VERSION,
                                            metadata={"thread_id": body.thread_id},
                                        )
                                    )
                            except Exception:
                                pass

                        asyncio.create_task(_save_cache_entry())

            # Background AI title generation if needed
            title_updated = False
            if current_title in ("New Conversation", "New Chat", ""):
                asyncio.create_task(_generate_and_save_title(pool, body.thread_id))
                title_updated = True

            yield f"event: done\ndata: {json.dumps({'thread_id': body.thread_id, 'title_updated': title_updated, 'interrupted': is_interrupted, 'cached': False})}\n\n"


        except Exception as e:
            logger.exception("Error during chat stream: %s", e)
            yield f"event: error\ndata: {json.dumps({'message': str(e) or 'Streaming failed'})}\n\n"
        finally:
            await release_thread(body.thread_id)


    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/resume")
async def chat_resume(
    body: ChatResumeRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    pool = await get_db_pool()
    bot = await get_chatbot()

    async with pool.connection() as conn:
        await verify_thread_ownership(conn, body.thread_id, current_user.user_id)

    if not await acquire_thread(body.thread_id):
        raise HTTPException(
            status_code=409,
            detail="A request is already actively processing for this thread. Please wait for it to complete.",
        )

    config = {"configurable": {"thread_id": body.thread_id}}
    state = await bot.aget_state(config)
    has_interrupt = False
    if state.next and state.tasks:
        for task in state.tasks:
            if getattr(task, "interrupts", ()):
                has_interrupt = True
                break

    if not has_interrupt:
        await release_thread(body.thread_id)
        raise HTTPException(
            status_code=400,
            detail="No interrupted run waiting for approval on this thread.",
        )

    resume_command = Command(resume=body.decision)

    async def resume_event_generator() -> AsyncGenerator[str, None]:
        full_assistant_reply = []
        last_tool_name = None
        assistant_persisted = False
        is_interrupted = False

        try:
            async for event in bot.astream_events(
                resume_command,
                config=config,
                version="v2",
            ):
                if await request.is_disconnected():
                    break

                ev_type = event.get("event")

                if ev_type == "on_chat_model_stream":
                    chunk = event.get("data", {})["chunk"]
                    content = getattr(chunk, "content", None)
                    if isinstance(content, str) and content:
                        full_assistant_reply.append(content)
                        yield f"event: text\ndata: {json.dumps({'content': content})}\n\n"

                elif ev_type == "on_tool_start":
                    tool_name = event.get("name")
                    last_tool_name = tool_name
                    yield f"event: tool_start\ndata: {json.dumps({'name': tool_name})}\n\n"

                elif ev_type == "on_tool_end":
                    tool_name = event.get("name") or last_tool_name
                    yield f"event: tool_end\ndata: {json.dumps({'name': tool_name})}\n\n"

            state_after = await bot.aget_state(config)
            if state_after.next and state_after.tasks:
                for task in state_after.tasks:
                    if getattr(task, "interrupts", ()):
                        is_interrupted = True
                        interrupt_val = task.interrupts[0].value
                        yield f"event: interrupt\ndata: {json.dumps({'thread_id': body.thread_id, 'interrupt': interrupt_val})}\n\n"
                        break

            if full_assistant_reply and not assistant_persisted and not is_interrupted:
                final_text = "".join(full_assistant_reply).strip()
                if final_text:
                    async with pool.connection() as conn:
                        await conn.execute(
                            """
                            INSERT INTO chat_messages (thread_id, role, content, tool_name)
                            VALUES (%s, 'assistant', %s, %s)
                            """,
                            (body.thread_id, final_text, last_tool_name),
                        )
                        await conn.execute(
                            "UPDATE chat_threads SET updated_at = CURRENT_TIMESTAMP WHERE thread_id = %s",
                            (body.thread_id,),
                        )
                    assistant_persisted = True

            yield f"event: done\ndata: {json.dumps({'thread_id': body.thread_id, 'title_updated': False, 'interrupted': is_interrupted})}\n\n"

        except Exception as e:
            logger.exception("Error during resume stream: %s", e)
            yield f"event: error\ndata: {json.dumps({'message': str(e) or 'Resume stream failed'})}\n\n"
        finally:
            await release_thread(body.thread_id)

    return StreamingResponse(
        resume_event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
