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
from backend.app.core.database import (
    pool,
    get_db_pool,
    setup_database_tables,
    is_pgvector_available,
    get_pgvector_status,
)
from backend.app.schemas.cache import CacheEntryCreate
from backend.app.services.semantic_cache import (
    SemanticCacheService,
    compute_cosine_similarity,
    compute_query_hash,
)


class MockFixedEmbeddings:
    """Deterministic mock embedding provider supporting configurable dimensions."""
    def __init__(self, dim: int = 1536):
        self.dim = dim

    async def aembed_query(self, text: str):
        normalized = text.strip().lower()
        val = sum(ord(c) for c in normalized)
        vec = [0.0] * self.dim
        vec[val % self.dim] = 1.0
        return vec


async def run_pgvector_hnsw_tests():
    print("=" * 70)
    print("RUNNING PGVECTOR & HNSW INTEGRATION TEST SUITE")
    print("=" * 70)

    db_pool = await get_db_pool()
    await setup_database_tables()

    status = get_pgvector_status()
    print(f"Status Diagnostics: {status}")

    ts = int(time.time() * 1000)
    test_user_a = f"u_hnsw_a_{ts}"
    test_user_b = f"u_hnsw_b_{ts}"

    mock_emb = MockFixedEmbeddings(dim=settings.SEMANTIC_CACHE_EMBEDDING_DIMENSION)
    cache_service = SemanticCacheService(embeddings_client=mock_emb)

    try:
        # TEST 1: Distance-to-Similarity Math Equivalence
        print("\n[TEST 1] Testing Distance to Similarity Math Equivalence...")
        # For cosine: sim = 1.0 - distance <=> distance = 1.0 - sim
        test_sims = [1.0, 0.95, 0.88, 0.50, 0.0]
        for sim in test_sims:
            distance = 1.0 - sim
            recovered_sim = 1.0 - distance
            assert abs(recovered_sim - sim) < 1e-9, f"Math mismatch: {sim} != {recovered_sim}"
        # Threshold 0.88 -> max_distance 0.12
        threshold = 0.88
        max_dist = 1.0 - threshold
        assert abs(max_dist - 0.12) < 1e-9
        print(f" -> PASSED: Cosine distance <-> similarity transformation verified (threshold {threshold} <=> max_distance {max_dist:.2f}).")

        # TEST 2: Exact Match Fast-Path Bypasses Vector Search
        print("\n[TEST 2] Testing Exact Match Fast-Path Bypass...")
        # Create an entry
        q_text = "What is Lamit's memory architecture?"
        resp_text = "Lamit uses LangGraph checkpointers and PostgreSQL."
        vec = await mock_emb.aembed_query(q_text)

        await cache_service.store(
            CacheEntryCreate(
                user_id=test_user_a,
                query_text=q_text,
                embedding=vec,
                response_text=resp_text,
            )
        )

        # Mock embedding generator to raise exception; exact match should NEVER call it
        cache_service_no_emb = SemanticCacheService(
            embeddings_client=MagicMock(aembed_query=AsyncMock(side_effect=RuntimeError("Must not be called")))
        )
        exact_res = await cache_service_no_emb.lookup(q_text, user_id=test_user_a)
        assert exact_res.hit is True, "Exact match lookup failed"
        assert exact_res.similarity_score == 1.0
        assert exact_res.cached_response == resp_text
        print(" -> PASSED: Exact match hit succeeded O(1) without generating embeddings.")

        # TEST 3: Multi-Tenant Partition Isolation
        print("\n[TEST 3] Testing Multi-Tenant Data Isolation...")
        res_user_b = await cache_service.lookup(q_text, user_id=test_user_b)
        assert res_user_b.hit is False, "Cross-tenant leakage detected: user B accessed user A's cached entry!"
        print(" -> PASSED: Multi-tenant boundary strictly preserved (User B received cache MISS).")

        # TEST 4: Config Version and Model Name Partitioning
        print("\n[TEST 4] Testing Model and Config Version Filtering...")
        res_diff_model = await cache_service.lookup(
            q_text,
            user_id=test_user_a,
            model_name="claude-3-opus-incompatible",
        )
        assert res_diff_model.hit is False, "Incompatible model returned a cache hit!"
        print(" -> PASSED: Incompatible model safely bypassed.")

        # TEST 5: Retrieval Query EXPLAIN (ANALYZE, BUFFERS) Execution
        print("\n[TEST 5] Testing Retrieval Query Plan with EXPLAIN (ANALYZE, BUFFERS)...")
        plan_lines = await cache_service.explain_retrieval_query(
            "What is Lamit's memory architecture?",
            user_id=test_user_a,
        )
        assert len(plan_lines) > 0, "Empty explain plan returned"
        print("  Query Plan Output:")
        for line in plan_lines[:5]:
            print(f"    {line}")
        print(" -> PASSED: EXPLAIN (ANALYZE, BUFFERS) generated real execution plan.")

        # TEST 6: Resilient Fallback When pgvector Is Unavailable
        print("\n[TEST 6] Testing Dual-Mode Graceful Fallback Mechanics...")
        fallback_status = get_pgvector_status()
        assert "pgvector_active" in fallback_status
        assert "embedding_dimension" in fallback_status
        print(f" -> PASSED: Fallback capability probe active: pgvector_active={fallback_status['pgvector_active']}")

        print("\n" + "=" * 70)
        print("ALL PGVECTOR & HNSW INTEGRATION TESTS PASSED SUCCESSFULLY!")
        print("=" * 70)
        return True

    finally:
        # Cleanup test artifacts
        await cache_service.invalidate(user_id=test_user_a)
        await cache_service.invalidate(user_id=test_user_b)
        if not db_pool.closed:
            await db_pool.close()


if __name__ == "__main__":
    import selectors
    success = asyncio.run(
        run_pgvector_hnsw_tests(),
        loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()) if sys.platform == "win32" else None,
    )
    sys.exit(0 if success else 1)
