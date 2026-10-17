import asyncio
import os
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

_root = str(Path(__file__).resolve().parent.parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

from backend.app.core.config import settings
from backend.app.core.database import pool, get_db_pool, setup_database_tables
from backend.app.schemas.cache import CacheEntryCreate
from backend.app.services.semantic_cache import (
    SemanticCacheService,
    compute_cosine_similarity,
    compute_query_hash,
    NON_CACHEABLE_TOOLS,
)


class MockEmbeddings:
    """Deterministic mock embedding provider for tests to avoid paid OpenAI API calls."""
    def __init__(self, vector_map=None):
        self.vector_map = vector_map or {}

    async def aembed_query(self, text: str):
        normalized = text.strip().lower()
        if normalized in self.vector_map:
            return self.vector_map[normalized]
        val = sum(ord(c) for c in normalized)
        vec = [0.0] * 8
        vec[val % 8] = 1.0
        return vec


async def run_semantic_cache_tests():
    print("=" * 70)
    print("RUNNING SEMANTIC CACHE VERIFICATION TEST SUITE")
    print("=" * 70)

    db_pool = await get_db_pool()
    await setup_database_tables()

    ts = int(time.time() * 1000)
    user_t2 = f"u_t2_{ts}"
    user_t3 = f"u_t3_{ts}"
    user_t4_a = f"u_t4_a_{ts}"
    user_t4_b = f"u_t4_b_{ts}"
    user_t5 = f"u_t5_{ts}"
    user_t7 = f"u_t7_{ts}"
    user_t8 = f"u_t8_{ts}"

    try:
        # TEST 1: Math Cosine Similarity Helper
        print("\n[TEST 1] Verifying Vector Cosine Math Helper...")
        v1 = [1.0, 0.0, 0.0]
        v2 = [1.0, 0.0, 0.0]
        v3 = [0.0, 1.0, 0.0]
        v4 = [0.7071, 0.7071, 0.0]
        assert abs(compute_cosine_similarity(v1, v2) - 1.0) < 1e-4
        assert abs(compute_cosine_similarity(v1, v3) - 0.0) < 1e-4
        assert abs(compute_cosine_similarity(v1, v4) - 0.7071) < 1e-3
        assert compute_cosine_similarity([], []) == 0.0
        print(" -> PASSED: Cosine similarity mathematics verified.")

        # TEST 2: Exact Match Cache Hit
        print("\n[TEST 2] Verifying Exact Query Hash Match (O(1) fast-path)...")
        mock_emb = MockEmbeddings()
        cache = SemanticCacheService(embeddings_client=mock_emb, similarity_threshold=0.88)
        query = "What is the capital of France?"
        answer = "The capital of France is Paris."
        vec = await mock_emb.aembed_query(query)

        cid = await cache.store(
            CacheEntryCreate(
                user_id=user_t2,
                query_text=query,
                response_text=answer,
                embedding=vec,
                model_name=settings.MODEL_NAME,
            )
        )
        assert cid is not None, "Failed to store cache entry"

        hit = await cache.lookup(query=query, user_id=user_t2)
        assert hit.hit is True, "Exact query should hit cache"
        assert hit.cached_response == answer
        assert hit.similarity_score == 1.0
        assert hit.cache_id == cid
        print(" -> PASSED: Exact match returned expected cached response.")

        # TEST 3: Semantic Similarity Hit vs Miss (Thresholding)
        print("\n[TEST 3] Verifying Semantic Similarity Thresholding (0.88)...")
        mock_emb_sem = MockEmbeddings(
            vector_map={
                "how do i write a python decorator": [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                "how to create a decorator in python": [0.95, 0.3122, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                "how to cook pasta": [0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            }
        )
        cache_sem = SemanticCacheService(embeddings_client=mock_emb_sem, similarity_threshold=0.88)
        base_q = "how do i write a python decorator"
        cached_ans = "A Python decorator wraps a function to modify its behavior."
        base_vec = await mock_emb_sem.aembed_query(base_q)

        await cache_sem.store(
            CacheEntryCreate(
                user_id=user_t3,
                query_text=base_q,
                response_text=cached_ans,
                embedding=base_vec,
                model_name=settings.MODEL_NAME,
            )
        )

        # Semantically similar -> HIT
        close_q = "how to create a decorator in python"
        sem_hit = await cache_sem.lookup(query=close_q, user_id=user_t3)
        assert sem_hit.hit is True, "Similar query should hit semantic cache"
        assert sem_hit.cached_response == cached_ans
        assert sem_hit.similarity_score >= 0.88
        print(f" -> PASSED: Semantic hit with score {sem_hit.similarity_score:.4f} >= 0.88 threshold.")

        # Semantically dissimilar -> MISS
        far_q = "how to cook pasta"
        sem_miss = await cache_sem.lookup(query=far_q, user_id=user_t3)
        assert sem_miss.hit is False, "Dissimilar query should miss cache"
        assert sem_miss.cached_response is None
        print(" -> PASSED: Dissimilar query correctly missed cache.")

        # TEST 4: Multi-Tenant / User Data Isolation
        print("\n[TEST 4] Verifying Multi-Tenant User Isolation...")
        secret_q = "What is my credit score?"
        secret_ans = "Your credit score is 780."
        sec_vec = await mock_emb.aembed_query(secret_q)

        await cache.store(
            CacheEntryCreate(
                user_id=user_t4_a,
                query_text=secret_q,
                response_text=secret_ans,
                embedding=sec_vec,
            )
        )

        # Lookup by User A
        user_a_res = await cache.lookup(query=secret_q, user_id=user_t4_a)
        assert user_a_res.hit is True
        assert user_a_res.cached_response == secret_ans

        # Lookup by User B with same question
        user_b_res = await cache.lookup(query=secret_q, user_id=user_t4_b)
        assert user_b_res.hit is False, "User B must NEVER receive User A's cached private data"
        assert user_b_res.cached_response is None
        print(" -> PASSED: Cross-tenant data isolation strictly enforced (zero leakage).")

        # TEST 5: TTL Expiration and Invalidation
        print("\n[TEST 5] Verifying TTL Expiration and Invalidation...")
        cache_ttl = SemanticCacheService(embeddings_client=mock_emb, ttl_seconds=1)
        ttl_q = "What is ephemeral?"
        ttl_ans = "Ephemeral means lasting for a very short time."
        ttl_vec = await mock_emb.aembed_query(ttl_q)

        await cache_ttl.store(
            CacheEntryCreate(
                user_id=user_t5,
                query_text=ttl_q,
                response_text=ttl_ans,
                embedding=ttl_vec,
                ttl_seconds=1,
            )
        )

        # Immediate lookup -> HIT
        assert (await cache_ttl.lookup(query=ttl_q, user_id=user_t5)).hit is True

        # Wait for TTL to lapse
        await asyncio.sleep(1.2)

        # Post-expiry lookup -> MISS
        post_ttl = await cache_ttl.lookup(query=ttl_q, user_id=user_t5)
        assert post_ttl.hit is False, "Expired cache record must not be returned"

        # Invalidation cleans up
        deleted_count = await cache_ttl.invalidate()
        assert deleted_count >= 1
        print(" -> PASSED: TTL expiration and invalidation verified.")

        # TEST 6: Tool Dependency and Non-Cacheable Answers
        print("\n[TEST 6] Verifying Tool Ineligibility & HITL Interrupt Guards...")
        # Dynamic tools
        for tool_name in ["get_weather", "get_stock_price", "duckduckgo_search", "google_search", "send_gmail_message", "read_gmail_messages"]:
            assert cache.is_response_cacheable([tool_name], is_interrupted=False, response_text="Answer") is False, f"Tool {tool_name} should be ineligble"

        # HITL interrupt
        assert cache.is_response_cacheable([], is_interrupted=True, response_text="Pending approval") is False
        # Empty text
        assert cache.is_response_cacheable([], is_interrupted=False, response_text="") is False
        # Clean conversational answer
        assert cache.is_response_cacheable([], is_interrupted=False, response_text="Pure conversation") is True
        print(" -> PASSED: Dynamic tools, side effects, and interrupts correctly prevented from caching.")

        # TEST 7: Graceful Fallback on Failures
        print("\n[TEST 7] Verifying Graceful Fallback on API / Database Outages...")
        failing_emb = MagicMock()
        failing_emb.aembed_query = AsyncMock(side_effect=RuntimeError("OpenAI API Outage"))
        fallback_cache = SemanticCacheService(embeddings_client=failing_emb)

        fb_res = await fallback_cache.lookup(query="outage query", user_id=user_t7)
        assert fb_res.hit is False, "Failed embedding must safely result in cache miss"

        failing_pool = MagicMock()
        failing_pool.connection = MagicMock(side_effect=Exception("Database Connection Timeout"))
        fb_db_res = await fallback_cache.lookup(query="outage query", user_id=user_t7, custom_pool=failing_pool)
        assert fb_db_res.hit is False, "Failed DB must safely result in cache miss without throwing"
        print(" -> PASSED: Outages and lookup errors cleanly fall back to LLM pipeline.")

        # TEST 8: Concurrent Writes & Duplicate Lookup
        print("\n[TEST 8] Verifying Concurrency & Duplicate Operations...")
        async def concurrent_op(idx: int):
            q_text = f"Concurrent test question {idx}"
            a_text = f"Concurrent test answer {idx}"
            v = await mock_emb.aembed_query(q_text)
            c_id = await cache.store(
                CacheEntryCreate(
                    user_id=user_t8,
                    query_text=q_text,
                    response_text=a_text,
                    embedding=v,
                )
            )
            lookup_res = await cache.lookup(query=q_text, user_id=user_t8)
            return c_id is not None and lookup_res.hit

        results = await asyncio.gather(*(concurrent_op(i) for i in range(8)))
        assert all(results), "All concurrent store/lookup operations should succeed"
        print(" -> PASSED: Concurrency handled safely without locks or deadlocks.")

    finally:
        # Cleanup
        async with db_pool.connection() as conn:
            await conn.execute("DELETE FROM semantic_cache WHERE user_id LIKE %s", (f"%_{ts}",))
        if not db_pool.closed:
            await db_pool.close()



    print("\n" + "=" * 70)
    print("ALL SEMANTIC CACHE VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    import selectors
    asyncio.run(
        run_semantic_cache_tests(),
        loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()) if sys.platform == "win32" else None,
    )
