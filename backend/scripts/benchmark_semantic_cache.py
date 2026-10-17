#!/usr/bin/env python3
"""
Lamit Semantic Caching Performance & Recall Benchmark
Empirically measures:
  1. Exact-match latency (O(1) SHA-256 B-tree fast path)
  2. Semantic retrieval latency (vector cosine search)
  3. Recall fidelity against exact-search baseline
  4. Cache-hit rate under realistic mixed-traffic distribution
  5. PostgreSQL index and relation storage footprint
  6. Detailed EXPLAIN (ANALYZE, BUFFERS) query planner execution profile
"""

import asyncio
import os
import random
import statistics
import sys
import time
from pathlib import Path
from typing import List, Dict, Any

_root = str(Path(__file__).resolve().parent.parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

import psycopg
from psycopg.rows import dict_row

from backend.app.core.config import settings
from backend.app.core.database import (
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


class SyntheticBenchmarkEmbeddings:
    """Fast deterministic embedding generator for reproducible benchmarking."""
    def __init__(self, dim: int = 1536):
        self.dim = dim

    async def aembed_query(self, text: str) -> List[float]:
        # Deterministic pseudo-random normalized vector based on seed from text
        rng = random.Random(text.strip().lower())
        raw = [rng.gauss(0, 1) for _ in range(self.dim)]
        norm = sum(x * x for x in raw) ** 0.5
        return [x / norm for x in raw]


def perturb_vector(vec: List[float], similarity_target: float = 0.95) -> List[float]:
    """Generates a query vector with known target similarity to the base vector."""
    dim = len(vec)
    noise = [random.gauss(0, 1) for _ in range(dim)]
    norm_n = sum(x * x for x in noise) ** 0.5
    noise = [x / norm_n for x in noise]

    # Gram-Schmidt to make noise orthogonal to vec
    dot = sum(v * n for v, n in zip(vec, noise))
    ortho = [n - dot * v for v, n in zip(vec, noise)]
    norm_o = sum(x * x for x in ortho) ** 0.5
    ortho = [x / norm_o for x in ortho]

    # Combine: target * vec + sqrt(1 - target^2) * ortho
    weight_ortho = max(0.0, 1.0 - similarity_target ** 2) ** 0.5
    blended = [similarity_target * v + weight_ortho * o for v, o in zip(vec, ortho)]
    norm_b = sum(x * x for x in blended) ** 0.5
    return [x / norm_b for x in blended]


async def run_benchmark():
    print("=" * 80)
    print("LAMIT SEMANTIC CACHING EMPIRICAL BENCHMARK SUITE")
    print("=" * 80)

    db_pool = await get_db_pool()
    await setup_database_tables()
    status = get_pgvector_status()

    print(f"PostgreSQL Deployment: {settings.POSTGRES_URI.split('@')[-1]}")
    print(f"pgvector Status: active={status['pgvector_active']}, iterative_scan={status['has_iterative_scan']}")
    print(f"Active Mode: {'HNSW Index Scan' if status['pgvector_active'] else 'ARRAY_FALLBACK (PL/pgSQL Cosine)'}")
    print(f"Embedding Dimension: {settings.SEMANTIC_CACHE_EMBEDDING_DIMENSION}")
    print(f"Similarity Threshold: {settings.SEMANTIC_CACHE_SIMILARITY_THRESHOLD}")
    print("-" * 80)

    dim = settings.SEMANTIC_CACHE_EMBEDDING_DIMENSION
    embedder = SyntheticBenchmarkEmbeddings(dim=dim)
    cache_svc = SemanticCacheService(embeddings_client=embedder)

    benchmark_tag = f"bench_{int(time.time())}"
    users = [f"u_bench_{i}_{benchmark_tag}" for i in range(5)]
    seed_queries = [
        "How do I configure PostgreSQL connection pooling in FastAPI?",
        "Explain the difference between LangGraph checkpointers and memory stores.",
        "What are the best practices for rate limiting SSE streaming endpoints?",
        "How does cosine distance relate to cosine similarity in pgvector?",
        "Can LangGraph handle human-in-the-loop interrupts during agent execution?",
        "Explain multi-tenant data isolation techniques in relational databases.",
        "What is the mathematical formulation of HNSW graph traversal?",
        "How do I invalidate expired cache entries using PostgreSQL TTL?",
        "What are the security implications of storing JWTs in cookies vs localStorage?",
        "How do I optimize Docker container builds for Python FastAPI applications?",
    ]

    try:
        # Phase 1: Populate Seed Data (Realistic multi-user volume)
        print("\n[PHASE 1] Seeding Multi-Tenant Cache Dataset...")
        total_seeded = 0
        cached_entries: List[Dict[str, Any]] = []

        for user_idx, user in enumerate(users):
            for q_idx, q_text in enumerate(seed_queries):
                vec = await embedder.aembed_query(q_text)
                resp = f"Comprehensive synthesized answer for query '{q_text}' (User: {user})"
                c_id = await cache_svc.store(
                    CacheEntryCreate(
                        user_id=user,
                        query_text=q_text,
                        embedding=vec,
                        response_text=resp,
                        model_name=settings.MODEL_NAME,
                        embedding_model=settings.SEMANTIC_CACHE_EMBEDDING_MODEL,
                        config_version=settings.SEMANTIC_CACHE_CONFIG_VERSION,
                        ttl_seconds=86400,
                    )
                )
                cached_entries.append({
                    "id": c_id,
                    "user_id": user,
                    "query_text": q_text,
                    "vector": vec,
                    "response": resp,
                })
                total_seeded += 1

        print(f"  -> Successfully seeded {total_seeded} cache records across {len(users)} users.")

        # Phase 2: Exact Match Latency Benchmark (O(1) SHA-256 Fast Path)
        print("\n[PHASE 2] Benchmarking Exact-Match Latency (200 requests)...")
        exact_latencies: List[float] = []

        for _ in range(200):
            entry = random.choice(cached_entries)
            t0 = time.perf_counter()
            res = await cache_svc.lookup(
                query=entry["query_text"],
                user_id=entry["user_id"],
            )
            lat = (time.perf_counter() - t0) * 1000
            assert res.hit is True and res.similarity_score == 1.0
            exact_latencies.append(lat)

        exact_mean = statistics.mean(exact_latencies)
        exact_p50 = statistics.median(exact_latencies)
        exact_p95 = sorted(exact_latencies)[int(len(exact_latencies) * 0.95)]
        exact_p99 = sorted(exact_latencies)[int(len(exact_latencies) * 0.99)]

        print(f"  -> Mean: {exact_mean:.3f} ms | P50: {exact_p50:.3f} ms | P95: {exact_p95:.3f} ms | P99: {exact_p99:.3f} ms")

        # Phase 3: Semantic Nearest-Neighbor Retrieval Latency Benchmark
        print("\n[PHASE 3] Benchmarking Semantic Vector Retrieval Latency (200 requests)...")
        # For semantic retrieval, we slightly rephrase the query so exact SHA-256 misses,
        # but semantic vector has high similarity (~0.93 - 0.96)
        semantic_latencies: List[float] = []
        semantic_hits = 0

        for i in range(200):
            entry = random.choice(cached_entries)
            # Query perturbation: add semantic nuance
            modified_query = f"{entry['query_text']} (Please elaborate further with detail #{i})"

            # Override embedder temporarily for this test query to return perturbed vector
            perturbed_vec = perturb_vector(entry["vector"], similarity_target=0.94)
            cache_svc._embeddings_client = type("MockPerturbed", (), {
                "aembed_query": lambda self, t, v=perturbed_vec: asyncio.sleep(0, result=v)
            })()

            t0 = time.perf_counter()
            res = await cache_svc.lookup(
                query=modified_query,
                user_id=entry["user_id"],
            )
            lat = (time.perf_counter() - t0) * 1000
            semantic_latencies.append(lat)
            if res.hit:
                semantic_hits += 1

        sem_mean = statistics.mean(semantic_latencies)
        sem_p50 = statistics.median(semantic_latencies)
        sem_p95 = sorted(semantic_latencies)[int(len(semantic_latencies) * 0.95)]
        sem_p99 = sorted(semantic_latencies)[int(len(semantic_latencies) * 0.99)]
        sem_hit_rate = (semantic_hits / 200) * 100

        print(f"  -> Mean: {sem_mean:.3f} ms | P50: {sem_p50:.3f} ms | P95: {sem_p95:.3f} ms | P99: {sem_p99:.3f} ms")
        print(f"  -> Semantic Hit Rate on Similar Variations: {sem_hit_rate:.1f}%")

        # Phase 4: Recall Verification against Brute-Force Baseline
        print("\n[PHASE 4] Verifying Recall against Exact Mathematical Baseline...")
        recall_correct = 0
        total_eval = 50

        for _ in range(total_eval):
            entry = random.choice(cached_entries)
            q_perturbed = perturb_vector(entry["vector"], similarity_target=0.95)

            # Brute-force baseline in Python
            best_id_baseline = None
            best_score_baseline = -1.0
            for cand in cached_entries:
                if cand["user_id"] == entry["user_id"]:
                    sim = compute_cosine_similarity(q_perturbed, cand["vector"])
                    if sim > best_score_baseline:
                        best_score_baseline = sim
                        best_id_baseline = cand["id"]

            # Database retrieval
            cache_svc._embeddings_client = type("MockPerturbed", (), {
                "aembed_query": lambda self, t, v=q_perturbed: asyncio.sleep(0, result=v)
            })()
            db_res = await cache_svc.lookup(
                query="recall_eval_query",
                user_id=entry["user_id"],
            )

            if best_score_baseline >= settings.SEMANTIC_CACHE_SIMILARITY_THRESHOLD:
                if db_res.hit and db_res.cache_id == best_id_baseline:
                    recall_correct += 1
            else:
                if not db_res.hit:
                    recall_correct += 1

        recall_pct = (recall_correct / total_eval) * 100
        print(f"  -> Recall Accuracy vs Mathematical Baseline: {recall_pct:.1f}% ({recall_correct}/{total_eval})")

        # Phase 5: Storage & Table Size Footprint Inspection
        print("\n[PHASE 5] Database Relation & Index Storage Footprint...")
        async with db_pool.connection() as conn:
            res_sizes = await conn.execute(
                """
                SELECT
                    pg_size_pretty(pg_relation_size('semantic_cache')) AS table_size,
                    pg_size_pretty(pg_indexes_size('semantic_cache'))  AS index_size,
                    pg_size_pretty(pg_total_relation_size('semantic_cache')) AS total_size,
                    (SELECT count(*) FROM semantic_cache) AS total_rows;
                """
            )
            size_data = await res_sizes.fetchone()
            print(f"  -> Total Cached Rows: {size_data['total_rows']}")
            print(f"  -> Table Data Size:   {size_data['table_size']}")
            print(f"  -> Indexes Size:      {size_data['index_size']}")
            print(f"  -> Total Footprint:   {size_data['total_size']}")

        # Phase 6: Query Plan & Buffer Reads Profile
        print("\n[PHASE 6] EXPLAIN (ANALYZE, BUFFERS) Execution Profile...")
        sample_entry = cached_entries[0]
        cache_svc._embeddings_client = embedder
        plan = await cache_svc.explain_retrieval_query(
            query="Explain semantic retrieval execution plan",
            user_id=sample_entry["user_id"],
        )
        for line in plan:
            print(f"  {line}")

        print("\n" + "=" * 80)
        print("EMPIRICAL BENCHMARK SUMMARY TABLE")
        print("=" * 80)
        print(f"{'Metric':<35} | {'Value'}")
        print("-" * 55)
        print(f"{'Exact-Match Latency (P50)':<35} | {exact_p50:.3f} ms")
        print(f"{'Exact-Match Latency (P95)':<35} | {exact_p95:.3f} ms")
        print(f"{'Semantic Retrieval Latency (P50)':<35} | {sem_p50:.3f} ms")
        print(f"{'Semantic Retrieval Latency (P95)':<35} | {sem_p95:.3f} ms")
        print(f"{'Recall Fidelity vs Exact Baseline':<35} | {recall_pct:.1f}%")
        print(f"{'Table Data Size':<35} | {size_data['table_size']}")
        print(f"{'Indexes Size':<35} | {size_data['index_size']}")
        print(f"{'Total Table Footprint':<35} | {size_data['total_size']}")
        print("=" * 80)

    finally:
        # Cleanup benchmark data
        print("\nCleaning up benchmark seed data...")
        async with db_pool.connection() as conn:
            await conn.execute("DELETE FROM semantic_cache WHERE user_id LIKE %s", (f"%_{benchmark_tag}",))
        if not db_pool.closed:
            await db_pool.close()
        print("Benchmark cleanup complete.")


if __name__ == "__main__":
    import selectors
    asyncio.run(
        run_benchmark(),
        loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()) if sys.platform == "win32" else None,
    )
