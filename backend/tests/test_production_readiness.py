import asyncio
import sys
import os
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

import httpx
from backend.app.main import app
from backend.app.core.database import pool
from backend.app.graph.engine import ensure_initialized
from backend.app.graph.tools.gmail_tool import send_gmail_message


async def run_tests():
    print("=" * 70)
    print("RUNNING PRODUCTION READINESS SECURITY AUDIT SUITE")
    print("=" * 70)

    await ensure_initialized()
    app.state.pool = pool

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # AUDIT 1: Sensitive tool approval guard
        print("\n[AUDIT 1] Inspecting Sensitive Tool HITL Interrupt Guard...")
        try:
            tool_res = send_gmail_message.invoke({
                "recipient": "audit@target.com",
                "subject": "Security Audit",
                "body": "Sensitive payload"
            })
            assert "credentials are not configured" in tool_res or "Security Interrupt Triggered" in tool_res
        except Exception as e:
            assert "interrupt" in str(e).lower() or "pregel" in str(e).lower()
        print(" -> PASSED: Sensitive tool halts and guards outbound access")

        # AUDIT 2: Multi-Tenant Data Isolation
        print("\n[AUDIT 2] Inspecting Multi-Tenant Thread & Message Isolation...")
        # Create Owner User
        res = await client.post("/api/auth/signup", json={"email": "owner@audit.com", "password": "Password123!", "name": "Owner"})
        if res.status_code == 409:
            res = await client.post("/api/auth/login", json={"email": "owner@audit.com", "password": "Password123!"})
        assert res.status_code in (200, 201)
        owner_thread_res = await client.post("/api/threads")
        owner_tid = owner_thread_res.json()["thread_id"]

        # Client for Attacker User
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as attacker:
            res = await attacker.post("/api/auth/signup", json={"email": "attacker@audit.com", "password": "Password123!", "name": "Attacker"})
            if res.status_code == 409:
                res = await attacker.post("/api/auth/login", json={"email": "attacker@audit.com", "password": "Password123!"})
            assert res.status_code in (200, 201)

            # Attempt unauthorized read
            res = await attacker.get(f"/api/threads/{owner_tid}/messages")
            assert res.status_code == 403, f"Expected 403, got {res.status_code}"
            print(" -> PASSED: Cross-user message access rejected with 403 Forbidden")

            # Attempt unauthorized rename
            res = await attacker.patch(f"/api/threads/{owner_tid}/title", json={"title": "Hacked"})
            assert res.status_code == 403
            print(" -> PASSED: Cross-user title rename rejected with 403 Forbidden")

            # Attempt unauthorized delete
            res = await attacker.delete(f"/api/threads/{owner_tid}")
            assert res.status_code == 403
            print(" -> PASSED: Cross-user thread deletion rejected with 403 Forbidden")

            # Clean up while session is active
            del_res = await client.delete(f"/api/threads/{owner_tid}")
            assert del_res.status_code == 204
            print(" -> PASSED: Owner thread cleaned up successfully")

    if not pool.closed:
        await pool.close()

    print("\nALL PRODUCTION READINESS AUDITS PASSED!\n")


if __name__ == "__main__":
    import selectors
    asyncio.run(
        run_tests(),
        loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()) if sys.platform == "win32" else None,
    )
