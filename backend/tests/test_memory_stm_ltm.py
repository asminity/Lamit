import asyncio
import json
import os
import sys
import time
from pathlib import Path

_root = str(Path(__file__).resolve().parent.parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

import httpx
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage, RemoveMessage

from backend.app.core.config import settings
from backend.app.core.database import pool, get_db_pool, setup_database_tables
from backend.app.graph.engine import ensure_initialized
from backend.app.graph.tokens import (
    count_text_tokens,
    count_message_tokens,
    count_messages_tokens,
    find_safe_split_indices,
    partition_messages_for_summary,
)
from backend.app.services.memory_service import MemoryService
from backend.app.schemas.memory import MemoryCreateRequest, MemoryUpdateRequest, MemoryType
from backend.app.main import app


class MockEmbeddings:
    """Deterministic mock embedding provider supporting configurable dimensions with word-overlap semantics."""
    def __init__(self, dim: int = 1536):
        self.dim = dim

    async def aembed_query(self, text: str):
        import re
        words = set(re.findall(r"\w+", text.strip().lower()))
        vec = [0.0] * self.dim
        for word in words:
            h = 0
            for ch in word:
                h = (h * 31 + ord(ch)) % self.dim
            vec[h] += 1.0
        norm = sum(x * x for x in vec) ** 0.5
        if norm > 0:
            return [x / norm for x in vec]
        vec[0] = 1.0
        return vec



class MockExtractionLLM:
    """Mock LLM returning deterministic structured extraction JSON."""
    async def ainvoke(self, messages):
        class MockResp:
            content = json.dumps({
                "memories": [
                    {
                        "memory_type": "preference",
                        "content": "User prefers dark mode and concise responses.",
                        "structured_data": {"key": "theme", "value": "dark"},
                        "importance": 0.8,
                        "confidence": 1.0,
                    }
                ]
            })
        return MockResp()


async def run_memory_architecture_tests():
    print("=" * 70)
    print("RUNNING STM & LTM MEMORY ARCHITECTURE COMPREHENSIVE TEST SUITE")
    print("=" * 70)

    db_pool = await get_db_pool()
    await setup_database_tables()
    await ensure_initialized()
    app.state.pool = pool

    ts = int(time.time() * 1000)
    user_a_id = f"user_stm_a_{ts}"
    user_b_id = f"user_stm_b_{ts}"

    mock_emb = MockEmbeddings(dim=settings.SEMANTIC_CACHE_EMBEDDING_DIMENSION)
    mock_llm = MockExtractionLLM()
    mem_service = MemoryService(
        embeddings_client=mock_emb,
        extraction_llm=mock_llm,
        similarity_threshold=0.60,
    )

    try:
        # ----------------------------------------------------------------------
        # TEST 1: Token Counting & Tool-Call/Result Consistency
        # ----------------------------------------------------------------------
        print("\n[TEST 1] Testing STM Token Counting & Tool Pair Partition Integrity...")
        
        # A. Basic token counting
        text = "Hello world from the STM token manager!"
        tokens = count_text_tokens(text)
        assert tokens > 0, "Token count should be positive"
        print(f" -> PASSED: count_text_tokens('{text}') = {tokens}")

        # B. Tool Pair Consistency
        # Create a conversation with tool calls
        msgs = [
            HumanMessage(id="h1", content="What is the weather in Paris?"),
            AIMessage(
                id="a1",
                content="",
                tool_calls=[{"id": "call_paris_geo", "name": "get_lat_long", "args": {"location": "Paris"}}],
            ),
            ToolMessage(id="t1", tool_call_id="call_paris_geo", content='{"lat": 48.8566, "lon": 2.3522}'),
            AIMessage(
                id="a2",
                content="",
                tool_calls=[{"id": "call_paris_wx", "name": "get_weather", "args": {"lat": 48.8566, "lon": 2.3522}}],
            ),
            ToolMessage(id="t2", tool_call_id="call_paris_wx", content='{"temp": 18, "condition": "Sunny"}'),
            AIMessage(id="a3", content="The weather in Paris is 18°C and Sunny."),
            HumanMessage(id="h2", content="Thank you! How about Tokyo?"),
            AIMessage(id="a4", content="Tokyo is 22°C and clear."),
        ]

        safe_splits = find_safe_split_indices(msgs)
        # Safe split should be at h2 (index 6), NOT in the middle of tool calls (indices 1, 2, 3, 4, 5)
        assert 6 in safe_splits, f"Index 6 (h2) must be a safe split. Found: {safe_splits}"
        for invalid_idx in [1, 2, 3, 4, 5]:
            assert invalid_idx not in safe_splits, f"Index {invalid_idx} breaks tool consistency and must NOT be safe!"
        print(f" -> PASSED: Safe split points strictly respected tool boundaries: {safe_splits}")

        # C. Partition messages for summary
        to_summarize, to_keep = partition_messages_for_summary(
            msgs,
            recent_token_budget=100,  # small budget forces Turn 1 into summary
            min_recent_turns=1,
        )
        assert len(to_summarize) == 6, f"Expected 6 messages in summary partition, got {len(to_summarize)}"
        assert len(to_keep) == 2, f"Expected 2 messages in keep partition, got {len(to_keep)}"
        assert to_keep[0].id == "h2" and to_keep[1].id == "a4"
        print(" -> PASSED: partition_messages_for_summary preserved Tokyo turn and safely isolated Paris tool chain.")

        # ----------------------------------------------------------------------
        # TEST 2: LTM Persistence, Structured Storage, and Deduplication
        # ----------------------------------------------------------------------
        print("\n[TEST 2] Testing LTM Persistence and Deduplication...")
        
        # A. Add a memory
        m1 = await mem_service.add_memory(
            user_id=user_a_id,
            memory_type=MemoryType.PREFERENCE.value,
            content="User prefers PostgreSQL over MongoDB for backend projects.",
            structured_data={"key": "database_preference", "value": "PostgreSQL"},
            importance=0.9,
            confidence=1.0,
            provenance={"thread_id": "t_001"},
        )
        assert m1.id is not None
        assert m1.user_id == user_a_id
        assert m1.is_active is True
        print(f" -> PASSED: Created memory id={m1.id} for user={user_a_id}")

        # B. Deduplication: Add exact same content
        m1_dup = await mem_service.add_memory(
            user_id=user_a_id,
            memory_type=MemoryType.PREFERENCE.value,
            content="User prefers PostgreSQL over MongoDB for backend projects.",
            structured_data={"key": "database_preference", "value": "PostgreSQL"},
            importance=0.9,
            confidence=1.0,
        )
        assert m1_dup.id == m1.id, "Duplicate memory should return existing id, not create new record"
        print(f" -> PASSED: Deduplication caught identical memory, preserved id={m1.id}")

        # ----------------------------------------------------------------------
        # TEST 3: LTM Conflict Detection and Supersession
        # ----------------------------------------------------------------------
        print("\n[TEST 3] Testing LTM Conflict Detection and Supersession...")

        # Add updated conflicting preference with the same key
        m2 = await mem_service.add_memory(
            user_id=user_a_id,
            memory_type=MemoryType.PREFERENCE.value,
            content="User decided to switch to CockroachDB for distributed workloads.",
            structured_data={"key": "database_preference", "value": "CockroachDB"},
            importance=0.95,
            confidence=1.0,
            provenance={"thread_id": "t_002"},
        )
        assert m2.id != m1.id
        assert m2.is_active is True

        # Verify old memory m1 is now inactive and superseded_by = m2.id
        async with db_pool.connection() as conn:
            res = await conn.execute(
                "SELECT is_active, superseded_by FROM user_memories WHERE id = %s",
                (m1.id,),
            )
            old_row = await res.fetchone()
            assert old_row["is_active"] is False, "Superseded memory must be marked is_active=False"
            assert old_row["superseded_by"] == m2.id, f"superseded_by must be {m2.id}, got {old_row['superseded_by']}"
        print(f" -> PASSED: Conflict correctly superseded old id={m1.id} with new id={m2.id}")

        # ----------------------------------------------------------------------
        # TEST 4: Multi-Tenant Data Isolation (Zero Leakage)
        # ----------------------------------------------------------------------
        print("\n[TEST 4] Testing Strict Multi-Tenant Data Isolation...")

        # Add memory for User B
        m_b = await mem_service.add_memory(
            user_id=user_b_id,
            memory_type=MemoryType.PROFILE.value,
            content="User B is a Chief Technology Officer at EnterpriseCorp.",
            structured_data={"role": "CTO"},
            importance=0.9,
        )
        assert m_b.user_id == user_b_id

        # Query memories for User A -> must NEVER return User B's memory
        memories_a = await mem_service.list_memories(user_id=user_a_id)
        assert all(m.user_id == user_a_id for m in memories_a), "Cross-tenant leak in list_memories!"
        assert not any(m.id == m_b.id for m in memories_a), "User A saw User B's memory!"

        # Semantic retrieval for User A querying User B's secret
        retrieved_a = await mem_service.retrieve_memories(
            user_id=user_a_id,
            query="Chief Technology Officer EnterpriseCorp",
        )
        assert not any(m.id == m_b.id for m in retrieved_a), "Semantic search leaked User B's memory to User A!"
        print(" -> PASSED: Multi-tenant boundary strictly prevents cross-user retrieval.")

        # User B cannot update or delete User A's memory
        del_attempt = await mem_service.delete_memory(user_id=user_b_id, memory_id=m2.id)
        assert del_attempt is False, "User B was able to delete User A's memory!"
        print(" -> PASSED: User B unauthorized deletion rejected.")

        # ----------------------------------------------------------------------
        # TEST 5: Cross-Thread Recall
        # ----------------------------------------------------------------------
        print("\n[TEST 5] Testing Cross-Thread Memory Recall...")

        # Memory stored from Thread 1
        m_project = await mem_service.add_memory(
            user_id=user_a_id,
            memory_type=MemoryType.PROJECT_KNOWLEDGE.value,
            content="The project codebase uses LangGraph with PostgreSQL checkpointer.",
            structured_data={"project": "Lamit", "framework": "LangGraph"},
            importance=0.85,
            provenance={"thread_id": "thread_alpha"},
        )

        # Retrieve in Thread Beta
        recalled = await mem_service.retrieve_memories(
            user_id=user_a_id,
            query="The project codebase uses LangGraph checkpointer in Lamit",
            similarity_threshold=0.25,
        )
        recalled_ids = [m.id for m in recalled]
        assert m_project.id in recalled_ids, f"Project memory {m_project.id} not recalled across threads! Got: {recalled_ids}"
        prompt_context = mem_service.format_memories_for_prompt(recalled)
        assert "LangGraph" in prompt_context
        print(f" -> PASSED: Successfully recalled across threads: '{m_project.content[:45]}...'")

        # ----------------------------------------------------------------------
        # TEST 6: Memory Soft & Hard Deletion
        # ----------------------------------------------------------------------
        print("\n[TEST 6] Testing Memory Deletion and Exclusion from Active Retrieval...")

        # Soft delete m_project
        del_res = await mem_service.delete_memory(user_id=user_a_id, memory_id=m_project.id, hard_delete=False)
        assert del_res is True

        # Now active retrieval must NOT return m_project
        recalled_after_del = await mem_service.retrieve_memories(
            user_id=user_a_id,
            query="The project codebase uses LangGraph checkpointer in Lamit",
            similarity_threshold=0.25,
        )
        assert m_project.id not in [m.id for m in recalled_after_del], "Deleted memory was returned in active retrieval!"

        print(" -> PASSED: Soft-deleted memory immediately excluded from retrieval.")

        # ----------------------------------------------------------------------
        # TEST 7: REST API Endpoints Verification (/api/memories)
        # ----------------------------------------------------------------------
        print("\n[TEST 7] Testing REST API Endpoints (/api/memories)...")

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # Login as test user
            email = f"mem_user_{ts}@example.com"
            pwd = "SecureMemoryPass123!"
            reg_res = await client.post("/api/auth/signup", json={"email": email, "password": pwd, "name": "MemUser"})
            if reg_res.status_code == 409:
                reg_res = await client.post("/api/auth/login", json={"email": email, "password": pwd})
            assert reg_res.status_code in (200, 201), f"Auth failed: {reg_res.text}"

            # Create memory via REST API
            create_res = await client.post(
                "/api/memories",
                json={
                    "memory_type": "preference",
                    "content": "User prefers pytest for unit testing and automated QA.",
                    "structured_data": {"test_runner": "pytest"},
                    "importance": 0.8,
                },
            )
            assert create_res.status_code == 201, f"Failed to create memory via API: {create_res.text}"
            api_mem = create_res.json()
            mem_id = api_mem["id"]
            print(f" -> PASSED: REST API POST /api/memories created memory id={mem_id}")

            # List memories via REST API
            list_res = await client.get("/api/memories")
            assert list_res.status_code == 200
            list_data = list_res.json()
            assert any(m["id"] == mem_id for m in list_data["memories"])
            print(" -> PASSED: REST API GET /api/memories listed created memory")

            # Update memory via REST API
            patch_res = await client.patch(
                f"/api/memories/{mem_id}",
                json={"importance": 0.95},
            )
            assert patch_res.status_code == 200
            assert patch_res.json()["importance"] == 0.95
            print(" -> PASSED: REST API PATCH /api/memories updated importance")

            # Delete memory via REST API
            del_api_res = await client.delete(f"/api/memories/{mem_id}")
            assert del_api_res.status_code == 204
            print(" -> PASSED: REST API DELETE /api/memories succeeded with 204 No Content")

        # Clean up database test records
        async with db_pool.connection() as conn:
            await conn.execute("DELETE FROM user_memories WHERE user_id IN (%s, %s)", (user_a_id, user_b_id))

        print("\n" + "=" * 70)
        print("ALL STM & LTM MEMORY ARCHITECTURE TESTS PASSED PERFECTLY!")
        print("=" * 70)

    finally:
        if not pool.closed:
            await pool.close()


if __name__ == "__main__":
    import selectors
    asyncio.run(
        run_memory_architecture_tests(),
        loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()) if sys.platform == "win32" else None,
    )
