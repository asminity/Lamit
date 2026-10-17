import asyncio
import sys
import os
from pathlib import Path

_root = str(Path(__file__).resolve().parent.parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

import httpx
from backend.app.main import app
from backend.app.core.database import pool
from backend.app.graph.engine import ensure_initialized


async def run_tests():
    print("--- 1. Initializing DB and App Lifespan ---")
    await ensure_initialized()
    app.state.pool = pool

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client_a:
        # A. Health Check (unauthenticated)
        res = await client_a.get("/health")
        assert res.status_code == 200, f"Health check failed: {res.text}"
        print("PASS: /health is accessible without auth")

        # B. Access /api/threads without session (Should fail with 401)
        res = await client_a.get("/api/threads")
        assert res.status_code == 401, f"Expected 401 Unauthorized, got: {res.status_code}"
        print("PASS: Unauthenticated request to /api/threads returned 401")

        # C. Signup User A
        email_a = "alice@example.com"
        pwd_a = "AliceSecurePass123!"
        res = await client_a.post("/api/auth/signup", json={"email": email_a, "password": pwd_a, "name": "Alice"})
        if res.status_code == 409:
            res = await client_a.post("/api/auth/login", json={"email": email_a, "password": pwd_a})
        assert res.status_code in (200, 201), f"Signup/Login A failed: {res.text}"
        user_a = res.json()
        print(f"PASS: User A authenticated: id={user_a['id']}, email={user_a['email']}")
        assert "session_token" in client_a.cookies, "Session cookie not set for User A"
        print("PASS: HTTP-only session cookie set on client_a")

        # D. Get current user profile (/api/auth/me)
        res = await client_a.get("/api/auth/me")
        assert res.status_code == 200
        assert res.json()["email"] == email_a
        print("PASS: /api/auth/me returns User A details")

        # E. Create Thread for User A
        res = await client_a.post("/api/threads")
        assert res.status_code == 201, f"Failed to create thread for A: {res.text}"
        thread_a_id = res.json()["thread_id"]
        print(f"PASS: Created thread for User A: {thread_a_id}")

        # F. List threads for User A
        res = await client_a.get("/api/threads")
        assert res.status_code == 200
        threads_a = res.json()
        assert any(t["thread_id"] == thread_a_id for t in threads_a)
        print(f"PASS: User A sees their thread (count={len(threads_a)})")

        # G. Create separate client for User B
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client_b:
            res = await client_b.post("/api/auth/login", json={"email": "alice@example.com", "password": "wrongpassword"})
            assert res.status_code == 401
            print("PASS: Invalid password login returned 401")

            email_b = "bob@example.com"
            pwd_b = "BobSecurePass456!"
            res = await client_b.post("/api/auth/signup", json={"email": email_b, "password": pwd_b, "name": "Bob"})
            if res.status_code == 409:
                res = await client_b.post("/api/auth/login", json={"email": email_b, "password": pwd_b})
            assert res.status_code in (200, 201), f"Signup/Login B failed: {res.text}"
            user_b = res.json()
            print(f"PASS: User B authenticated: id={user_b['id']}, email={user_b['email']}")

            # H. User B lists threads -> must NOT see User A's thread!
            res = await client_b.get("/api/threads")
            assert res.status_code == 200
            threads_b = res.json()
            assert not any(t["thread_id"] == thread_a_id for t in threads_b), "DATA LEAK: User B can see User A's thread!"
            print("PASS: Data Isolation - User B's thread list excludes User A's thread")

            # I. User B tries to read User A's messages -> must be 403 Forbidden!
            res = await client_b.get(f"/api/threads/{thread_a_id}/messages")
            assert res.status_code == 403, f"Expected 403 Forbidden, got {res.status_code}: {res.text}"
            print("PASS: Data Isolation - User B cannot view User A's messages (403 Forbidden)")

            # J. User B tries to update User A's thread title -> must be 403 Forbidden!
            res = await client_b.patch(f"/api/threads/{thread_a_id}/title", json={"title": "Hacked Title"})
            assert res.status_code == 403, f"Expected 403 Forbidden, got {res.status_code}: {res.text}"
            print("PASS: Data Isolation - User B cannot modify User A's thread (403 Forbidden)")

            # K. User B tries to delete User A's thread -> must be 403 Forbidden!
            res = await client_b.delete(f"/api/threads/{thread_a_id}")
            assert res.status_code == 403, f"Expected 403 Forbidden, got {res.status_code}: {res.text}"
            print("PASS: Data Isolation - User B cannot delete User A's thread (403 Forbidden)")

            # L. User B logs out
            res = await client_b.post("/api/auth/logout")
            assert res.status_code == 200
            print("PASS: User B logged out successfully")

            # M. After logout, requests are 401
            res = await client_b.get("/api/threads")
            assert res.status_code == 401
            print("PASS: User B session invalidated after logout (401)")

        # Clean up User A's thread
        res = await client_a.delete(f"/api/threads/{thread_a_id}")
        assert res.status_code == 204
        print("PASS: User A successfully deleted their own thread")

    if not pool.closed:
        await pool.close()

    print("\nALL BACKEND AUTH & DATA ISOLATION TESTS PASSED PERFECTLY!\n")


if __name__ == "__main__":
    import selectors
    asyncio.run(
        run_tests(),
        loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()) if sys.platform == "win32" else None,
    )
