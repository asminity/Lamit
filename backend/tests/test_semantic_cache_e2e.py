import asyncio
import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

_root = str(Path(__file__).resolve().parent.parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

import httpx
from backend.app.main import app
from backend.app.core.database import pool, get_db_pool, setup_database_tables
from backend.app.graph.engine import ensure_initialized
from backend.app.services.semantic_cache import semantic_cache


async def run_e2e_tests():
    print("=" * 70)
    print("RUNNING SEMANTIC CACHE END-TO-END (E2E) STREAMING TESTS")
    print("=" * 70)

    db_pool = await get_db_pool()
    await ensure_initialized()
    app.state.pool = db_pool

    ts = int(time.time() * 1000)
    user_email_1 = f"cache_tester_1_{ts}@example.com"
    user_email_2 = f"cache_tester_2_{ts}@example.com"

    transport = httpx.ASGITransport(app=app)

    # Deterministic mock embedding function
    async def mock_aembed_query(text: str):
        normalized = text.strip().lower()
        if "france" in normalized:
            return [1.0, 0.0, 0.0, 0.0]
        elif "paris" in normalized:
            return [0.96, 0.28, 0.0, 0.0]
        return [0.0, 1.0, 0.0, 0.0]

    with patch.object(semantic_cache, "get_embedding", side_effect=mock_aembed_query):
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver", timeout=60.0) as client1:
            # 1. Sign up User 1
            res1 = await client1.post("/api/auth/signup", json={"email": user_email_1, "password": "Password123!", "name": "User 1"})
            assert res1.status_code in (200, 201), f"Auth failed: {res1.text}"
            u1_id = res1.json()["id"]
            print(f"PASS: Authenticated User 1 ({u1_id})")

            # 2. Create thread for User 1
            t_res = await client1.post("/api/threads")
            assert t_res.status_code == 201
            thread_id_1 = t_res.json()["thread_id"]
            print(f"PASS: Created thread for User 1 ({thread_id_1})")

            # 3. First Turn: Should be CACHE MISS (generates response from mock/LLM)
            query_1 = "What is the capital of France?"
            mock_llm_reply = "The capital of France is Paris."

            # Pre-store an eligible entry into the semantic cache for User 1 to simulate a previously cached answer
            from backend.app.schemas.cache import CacheEntryCreate
            from backend.app.core.config import settings
            emb1 = await mock_aembed_query(query_1)
            await semantic_cache.store(
                CacheEntryCreate(
                    user_id=u1_id,
                    query_text=query_1,
                    response_text=mock_llm_reply,
                    embedding=emb1,
                    model_name=settings.MODEL_NAME,
                )
            )
            print("PASS: Seeded initial semantic cache entry for User 1")

            # 4. Turn 2: Semantically similar query from User 1 -> CACHE HIT
            query_2 = "What city is the capital in Paris, France?"
            events = []
            async with client1.stream(
                "POST",
                "/api/chat/stream",
                json={"thread_id": thread_id_1, "message": query_2},
            ) as stream_res:
                assert stream_res.status_code == 200
                async for line in stream_res.aiter_lines():
                    if line.startswith("data: "):
                        events.append(json.loads(line[6:]))

            text_chunks = [e["content"] for e in events if "content" in e]
            reconstructed_text = "".join(text_chunks)
            done_event = next(e for e in events if "title_updated" in e)

            assert done_event.get("cached") is True, f"Expected cached=True, got {done_event}"
            assert done_event.get("similarity") is not None, "Expected similarity score in done event"
            assert done_event.get("similarity") >= 0.88, f"Expected similarity >= 0.88, got {done_event.get('similarity')}"
            assert reconstructed_text == mock_llm_reply
            print(f"PASS: Fast-path SSE stream returned cached response (similarity: {done_event['similarity']:.4f})")

            # 5. Check chat_messages persistence for User 1
            hist_res = await client1.get(f"/api/threads/{thread_id_1}/messages")
            assert hist_res.status_code == 200
            msgs = hist_res.json()["messages"]
            assert len(msgs) == 2, f"Expected 2 messages, got {len(msgs)}"
            assert msgs[0]["role"] == "user"
            assert msgs[0]["content"] == query_2
            assert msgs[1]["role"] == "assistant"
            assert msgs[1]["content"] == mock_llm_reply
            assert msgs[1]["tool_name"] == "semantic_cache"
            print("PASS: Cached turn correctly recorded in PostgreSQL chat_messages with tool_name='semantic_cache'")
            await client1.delete(f"/api/threads/{thread_id_1}")


        # 6. User 2 asks the EXACT same query -> MUST BE CACHE MISS
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver", timeout=60.0) as client2:
            res2 = await client2.post("/api/auth/signup", json={"email": user_email_2, "password": "Password123!", "name": "User 2"})
            assert res2.status_code in (200, 201)
            u2_id = res2.json()["id"]

            t2_res = await client2.post("/api/threads")
            thread_id_2 = t2_res.json()["thread_id"]

            # User 2 performs lookup directly in semantic cache
            cache_res_u2 = await semantic_cache.lookup(query=query_1, user_id=u2_id)
            assert cache_res_u2.hit is False, "User 2 must NOT hit User 1's cache entry"
            print("PASS: Cross-user query isolated; User 2 cannot access User 1's cached responses")

            # Clean up test thread for User 2
            await client2.delete(f"/api/threads/{thread_id_2}")


    # Cleanup DB
    async with db_pool.connection() as conn:
        await conn.execute("DELETE FROM semantic_cache WHERE user_id IN (%s, %s)", (u1_id, u2_id))
        await conn.execute("DELETE FROM users WHERE id IN (%s, %s)", (u1_id, u2_id))

    if not db_pool.closed:
        await db_pool.close()

    print("\n" + "=" * 70)
    print("ALL SEMANTIC CACHE E2E STREAMING TESTS PASSED SUCCESSFULLY!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    import selectors
    asyncio.run(
        run_e2e_tests(),
        loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()) if sys.platform == "win32" else None,
    )
