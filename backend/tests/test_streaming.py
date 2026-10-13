import asyncio
import json
import sys
import os
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

import httpx
from backend.app.main import app
from backend.app.core.database import pool
from backend.app.graph.engine import ensure_initialized, checkpointer


async def run_tests():
    print("=" * 70)
    print("RUNNING STREAMING VERIFICATION TESTS")
    print("=" * 70)

    await ensure_initialized()
    app.state.pool = pool

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver", timeout=60.0) as client:
        # 1. Authenticate user
        res = await client.post("/api/auth/signup", json={"email": "stream_tester@example.com", "password": "Password123!", "name": "Stream Tester"})
        if res.status_code == 409:
            res = await client.post("/api/auth/login", json={"email": "stream_tester@example.com", "password": "Password123!"})
        assert res.status_code in (200, 201), f"Auth failed: {res.text}"
        user_info = res.json()
        print(f"PASS: Authenticated tester user {user_info['id']}")

        # 2. Create thread
        t_res = await client.post("/api/threads")
        assert t_res.status_code == 201
        thread_id = t_res.json()["thread_id"]
        print(f"PASS: Created test thread: {thread_id}")

        # 3. Stream text
        events = []
        async with client.stream(
            "POST",
            "/api/chat/stream",
            json={"thread_id": thread_id, "message": "Reply with exactly 'Streaming verified.'"},
        ) as stream_res:
            assert stream_res.status_code == 200
            async for line in stream_res.aiter_lines():
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))

        assert any("content" in e for e in events), "No text token events received"
        print("PASS: Real-time SSE text streaming received tokens successfully")

        # 4. Check message history in database
        hist_res = await client.get(f"/api/threads/{thread_id}/messages")
        assert hist_res.status_code == 200
        msgs = hist_res.json()["messages"]
        assert len(msgs) >= 2, f"Expected user + assistant messages, got: {len(msgs)}"
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"
        print("PASS: Both turns persisted correctly in PostgreSQL chat_messages")

        # Clean up thread
        await client.delete(f"/api/threads/{thread_id}")

    if not pool.closed:
        await pool.close()

    print("\nALL STREAMING TESTS PASSED!\n")


if __name__ == "__main__":
    import selectors
    asyncio.run(
        run_tests(),
        loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()) if sys.platform == "win32" else None,
    )
