import asyncio
import json
import sys
import os
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

import httpx
from backend.app.main import app
from backend.app.core.database import pool
from backend.app.graph.engine import ensure_initialized


async def run_tests():
    print("=" * 80)
    print("FINAL END-TO-END VERIFICATION OF THE LANGGRAPH INTEGRATED WEB APPLICATION")
    print("=" * 80)

    await ensure_initialized()
    app.state.pool = pool

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver", timeout=60.0) as client:
        # 1. Health check
        print("\n[VERIFICATION 1] Testing Health & Database Connectivity...")
        h_res = await client.get("/health")
        assert h_res.status_code == 200
        h_data = h_res.json()
        assert h_data["status"] == "ok" and h_data["database"] == "connected"
        print(f" -> PASSED: Health endpoint OK: {h_data}")

        # 2. Authentication
        print("\n[VERIFICATION 2] Authenticating User...")
        res = await client.post("/api/auth/signup", json={"email": "e2e_tester@example.com", "password": "Password123!", "name": "E2E Tester"})
        if res.status_code == 409:
            res = await client.post("/api/auth/login", json={"email": "e2e_tester@example.com", "password": "Password123!"})
        assert res.status_code in (200, 201)
        print(" -> PASSED: Authenticated session active")

        # 3. Create Threads
        print("\n[VERIFICATION 3] Creating New Conversation Threads...")
        res_t1 = await client.post("/api/threads")
        assert res_t1.status_code == 201
        tid_1 = res_t1.json()["thread_id"]

        res_t2 = await client.post("/api/threads")
        assert res_t2.status_code == 201
        tid_2 = res_t2.json()["thread_id"]

        print(f" -> PASSED: Thread 1: {tid_1}, Thread 2: {tid_2}")

        # 4. Message Streaming
        print("\n[VERIFICATION 4] Verifying Real-Time SSE Token Streaming...")
        events_1 = []
        async with client.stream(
            "POST",
            "/api/chat/stream",
            json={"thread_id": tid_1, "message": "Hello AI! Reply with 'E2E Streaming Working'"},
        ) as s_res:
            assert s_res.status_code == 200
            async for line in s_res.aiter_lines():
                if line.startswith("data: "):
                    events_1.append(json.loads(line[6:]))

        assert any("content" in e for e in events_1)
        print(" -> PASSED: Tokens streamed successfully")

        # 5. History check
        print("\n[VERIFICATION 5] Verifying Full History Persistence...")
        hist_res = await client.get(f"/api/threads/{tid_1}/messages")
        assert hist_res.status_code == 200
        messages = hist_res.json()["messages"]
        assert len(messages) >= 2
        print(f" -> PASSED: Retrieved {len(messages)} persisted messages")

        # 6. Title rename
        print("\n[VERIFICATION 6] Verifying Thread Title Update...")
        patch_res = await client.patch(f"/api/threads/{tid_1}/title", json={"title": "Updated Test Title"})
        assert patch_res.status_code == 200
        assert patch_res.json()["title"] == "Updated Test Title"
        print(" -> PASSED: Title updated successfully")

        # 7. Clean up
        await client.delete(f"/api/threads/{tid_1}")
        await client.delete(f"/api/threads/{tid_2}")
        print("\n -> PASSED: Cleaned up test threads")

    if not pool.closed:
        await pool.close()

    print("\nALL FINAL E2E TESTS PASSED!\n")


if __name__ == "__main__":
    import selectors
    asyncio.run(
        run_tests(),
        loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()) if sys.platform == "win32" else None,
    )
