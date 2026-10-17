import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from langchain_openai import OpenAIEmbeddings

from backend.app.core.config import settings
from backend.app.core.database import (
    get_db_pool,
    is_pgvector_available,
    has_iterative_scan_support,
    get_pgvector_status,
)
from backend.app.schemas.cache import CacheLookupResult, CacheEntryCreate

logger = logging.getLogger("semantic_cache")

# Non-cacheable tool names: dynamic external data, private user state, or sensitive side-effects
NON_CACHEABLE_TOOLS: set[str] = {
    "get_weather",
    "get_lat_long",
    "get_stock_price",
    "duckduckgo_search",
    "google_search",
    "arxiv_search",
    "google_scholar_search",
    "youtube_tool",
    "amazon_tool",
    "read_gmail_messages",
    "send_gmail_message",
}


def compute_query_hash(query: str) -> str:
    """Computes a SHA-256 hash of normalized query text for exact matching."""
    normalized = " ".join(query.strip().lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def compute_cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Computes cosine similarity between two float vectors in Python as a fallback."""
    if len(vec_a) != len(vec_b) or not vec_a:
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = sum(a * a for a in vec_a) ** 0.5
    norm_b = sum(b * b for b in vec_b) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class SemanticCacheService:
    def __init__(
        self,
        embeddings_client: Optional[Any] = None,
        enabled: Optional[bool] = None,
        similarity_threshold: Optional[float] = None,
        ttl_seconds: Optional[int] = None,
        embedding_model: Optional[str] = None,
        config_version: Optional[str] = None,
    ):
        self.enabled = settings.SEMANTIC_CACHE_ENABLED if enabled is None else enabled
        self.similarity_threshold = (
            settings.SEMANTIC_CACHE_SIMILARITY_THRESHOLD
            if similarity_threshold is None
            else similarity_threshold
        )
        self.ttl_seconds = (
            settings.SEMANTIC_CACHE_TTL_SECONDS
            if ttl_seconds is None
            else ttl_seconds
        )
        self.embedding_model = (
            settings.SEMANTIC_CACHE_EMBEDDING_MODEL
            if embedding_model is None
            else embedding_model
        )
        self.config_version = (
            settings.SEMANTIC_CACHE_CONFIG_VERSION
            if config_version is None
            else config_version
        )
        self._embeddings_client = embeddings_client

    def get_embeddings_client(self):
        if self._embeddings_client is None:
            self._embeddings_client = OpenAIEmbeddings(
                model=self.embedding_model,
                api_key=settings.OPENAI_API_KEY,
            )
        return self._embeddings_client

    async def get_embedding(self, text: str) -> Optional[List[float]]:
        """Generates embedding vector for a query with error handling."""
        try:
            client = self.get_embeddings_client()
            return await client.aembed_query(text.strip())
        except Exception as e:
            logger.warning(f"Failed to generate embedding: {type(e).__name__} - {e}")
            return None

    def is_response_cacheable(
        self,
        tool_names: Optional[List[str]] = None,
        is_interrupted: bool = False,
        response_text: Optional[str] = None,
    ) -> bool:
        """
        Safety audit to determine if a turn's response is eligible for semantic caching.
        """
        if not self.enabled:
            return False
        if is_interrupted:
            return False
        if not response_text or not response_text.strip():
            return False

        if tool_names:
            for tool in tool_names:
                if tool and tool.strip() in NON_CACHEABLE_TOOLS:
                    logger.debug(f"Cache save skipped: tool '{tool}' is non-cacheable.")
                    return False

        return True

    async def lookup(
        self,
        query: str,
        user_id: str,
        model_name: Optional[str] = None,
        custom_pool: Optional[Any] = None,
    ) -> CacheLookupResult:
        """
        Searches semantic cache for semantically matching responses for this user.
        Gracefully returns hit=False on any failure.
        """
        if not self.enabled:
            return CacheLookupResult(hit=False)

        start_time = time.perf_counter()
        query_hash = compute_query_hash(query)
        target_model = model_name or settings.MODEL_NAME

        try:
            pool = custom_pool or await get_db_pool()

            # 1. Exact query hash lookup first (Fast path O(1))
            async with pool.connection() as conn:
                res = await conn.execute(
                    """
                    SELECT id, response_text, metadata, hit_count, query_text
                    FROM semantic_cache
                    WHERE user_id = %s
                      AND query_hash = %s
                      AND model_name = %s
                      AND config_version = %s
                      AND expires_at > CURRENT_TIMESTAMP
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (user_id, query_hash, target_model, self.config_version),
                )
                exact_row = await res.fetchone()

                if exact_row:
                    cache_id = exact_row["id"]
                    # Async update hit stats
                    await conn.execute(
                        """
                        UPDATE semantic_cache
                        SET hit_count = hit_count + 1, last_accessed_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                        """,
                        (cache_id,),
                    )
                    latency_ms = (time.perf_counter() - start_time) * 1000
                    logger.info(
                        f"Semantic cache EXACT HIT [id={cache_id}, user={user_id[:8]}..., "
                        f"latency={latency_ms:.2f}ms]"
                    )
                    return CacheLookupResult(
                        hit=True,
                        cached_response=exact_row["response_text"],
                        similarity_score=1.0,
                        matched_query=exact_row["query_text"],
                        cache_id=cache_id,
                        metadata=exact_row["metadata"] or {},
                    )

            # 2. Semantic vector similarity lookup
            query_embedding = await self.get_embedding(query)
            if query_embedding is None:
                return CacheLookupResult(hit=False)

            use_hnsw = is_pgvector_available() and len(query_embedding) == settings.SEMANTIC_CACHE_EMBEDDING_DIMENSION

            async with pool.connection() as conn:
                if use_hnsw:
                    max_distance = max(0.0, 1.0 - self.similarity_threshold)
                    vec_str = f"[{','.join(str(x) for x in query_embedding)}]"

                    # Set transaction-scoped HNSW parameters
                    await conn.execute(f"SET LOCAL hnsw.ef_search = {settings.SEMANTIC_CACHE_HNSW_EF_SEARCH};")
                    if has_iterative_scan_support():
                        await conn.execute("SET LOCAL hnsw.iterative_scan = 'relaxed_order';")

                    res = await conn.execute(
                        """
                        SELECT id, query_text, response_text, metadata, hit_count,
                               (1.0 - (embedding_vec <=> %s::vector)) AS similarity
                        FROM semantic_cache
                        WHERE user_id = %s
                          AND model_name = %s
                          AND embedding_model = %s
                          AND config_version = %s
                          AND expires_at > CURRENT_TIMESTAMP
                          AND (embedding_vec <=> %s::vector) <= %s
                        ORDER BY embedding_vec <=> %s::vector ASC
                        LIMIT 1
                        """,
                        (
                            vec_str,
                            user_id,
                            target_model,
                            self.embedding_model,
                            self.config_version,
                            vec_str,
                            max_distance,
                            vec_str,
                        ),
                    )
                else:
                    # High-performance array fallback with PL/pgSQL function
                    res = await conn.execute(
                        """
                        SELECT id, query_text, response_text, metadata, hit_count,
                               cosine_similarity_array(embedding, %s) AS similarity
                        FROM semantic_cache
                        WHERE user_id = %s
                          AND model_name = %s
                          AND embedding_model = %s
                          AND config_version = %s
                          AND expires_at > CURRENT_TIMESTAMP
                        ORDER BY similarity DESC
                        LIMIT 1
                        """,
                        (
                            query_embedding,
                            user_id,
                            target_model,
                            self.embedding_model,
                            self.config_version,
                        ),
                    )

                best_match = await res.fetchone()

                if best_match and best_match["similarity"] is not None:
                    similarity = float(best_match["similarity"])
                    if similarity >= self.similarity_threshold:
                        cache_id = best_match["id"]
                        await conn.execute(
                            """
                            UPDATE semantic_cache
                            SET hit_count = hit_count + 1, last_accessed_at = CURRENT_TIMESTAMP
                            WHERE id = %s
                            """,
                            (cache_id,),
                        )
                        latency_ms = (time.perf_counter() - start_time) * 1000
                        search_mode = "HNSW" if use_hnsw else "ARRAY_FALLBACK"
                        logger.info(
                            f"Semantic cache HIT [{search_mode}, id={cache_id}, score={similarity:.4f}, "
                            f"threshold={self.similarity_threshold}, latency={latency_ms:.2f}ms]"
                        )
                        return CacheLookupResult(
                            hit=True,
                            cached_response=best_match["response_text"],
                            similarity_score=similarity,
                            matched_query=best_match["query_text"],
                            cache_id=cache_id,
                            metadata=best_match["metadata"] or {},
                        )
                    else:
                        logger.debug(
                            f"Semantic cache MISS [score={similarity:.4f} < {self.similarity_threshold}]"
                        )

            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.info(f"Semantic cache MISS [user={user_id[:8]}..., latency={latency_ms:.2f}ms]")
            return CacheLookupResult(hit=False)

        except Exception as e:
            logger.exception(f"Semantic cache lookup failure (falling back to LLM): {e}")
            return CacheLookupResult(hit=False)

    async def store(
        self,
        entry: CacheEntryCreate,
        custom_pool: Optional[Any] = None,
    ) -> Optional[int]:
        """
        Stores an eligible query and response into PostgreSQL semantic cache with retention enforcement.
        Supports both pgvector and array fallback representations.
        """
        if not self.enabled:
            return None

        query_hash = compute_query_hash(entry.query_text)
        target_model = entry.model_name or settings.MODEL_NAME
        target_embedding_model = entry.embedding_model or self.embedding_model
        ttl = entry.ttl_seconds or self.ttl_seconds
        config_ver = entry.config_version or self.config_version

        try:
            pool = custom_pool or await get_db_pool()
            async with pool.connection() as conn:
                # 1. Enforce user cache retention / size limit if needed
                max_entries = settings.SEMANTIC_CACHE_MAX_ENTRIES_PER_USER
                res_count = await conn.execute(
                    "SELECT COUNT(*) as count FROM semantic_cache WHERE user_id = %s",
                    (entry.user_id,),
                )
                row_count = await res_count.fetchone()
                current_count = row_count["count"] if row_count else 0

                if current_count >= max_entries:
                    # Prune oldest / expired records for this user
                    await conn.execute(
                        """
                        DELETE FROM semantic_cache
                        WHERE id IN (
                            SELECT id FROM semantic_cache
                            WHERE user_id = %s
                            ORDER BY expires_at ASC, last_accessed_at ASC
                            LIMIT %s
                        )
                        """,
                        (entry.user_id, max(1, current_count - max_entries + 1)),
                    )

                # 2. Insert or update entry
                use_hnsw = is_pgvector_available() and len(entry.embedding) == settings.SEMANTIC_CACHE_EMBEDDING_DIMENSION
                if use_hnsw:
                    vec_str = f"[{','.join(str(x) for x in entry.embedding)}]"
                    res_insert = await conn.execute(
                        """
                        INSERT INTO semantic_cache (
                            user_id, scope, query_text, query_hash, embedding, embedding_vec,
                            response_text, model_name, embedding_model, config_version,
                            metadata, hit_count, expires_at
                        )
                        VALUES (
                            %s, %s, %s, %s, %s, %s::vector,
                            %s, %s, %s, %s,
                            %s, 0, CURRENT_TIMESTAMP + (%s || ' seconds')::INTERVAL
                        )
                        RETURNING id
                        """,
                        (
                            entry.user_id,
                            entry.scope,
                            entry.query_text.strip(),
                            query_hash,
                            entry.embedding,
                            vec_str,
                            entry.response_text.strip(),
                            target_model,
                            target_embedding_model,
                            config_ver,
                            json.dumps(entry.metadata),
                            str(ttl),
                        ),
                    )
                else:
                    res_insert = await conn.execute(
                        """
                        INSERT INTO semantic_cache (
                            user_id, scope, query_text, query_hash, embedding,
                            response_text, model_name, embedding_model, config_version,
                            metadata, hit_count, expires_at
                        )
                        VALUES (
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, 0, CURRENT_TIMESTAMP + (%s || ' seconds')::INTERVAL
                        )
                        RETURNING id
                        """,
                        (
                            entry.user_id,
                            entry.scope,
                            entry.query_text.strip(),
                            query_hash,
                            entry.embedding,
                            entry.response_text.strip(),
                            target_model,
                            target_embedding_model,
                            config_ver,
                            json.dumps(entry.metadata),
                            str(ttl),
                        ),
                    )
                inserted = await res_insert.fetchone()
                cache_id = inserted["id"] if inserted else None
                logger.info(f"Stored entry in semantic cache [id={cache_id}, user={entry.user_id[:8]}...]")
                return cache_id

        except Exception as e:
            logger.exception(f"Failed to store semantic cache entry: {e}")
            return None

    async def explain_retrieval_query(
        self,
        query: str,
        user_id: str,
        model_name: Optional[str] = None,
        custom_pool: Optional[Any] = None,
    ) -> List[str]:
        """
        Executes EXPLAIN (ANALYZE, BUFFERS) on the active retrieval query
        for diagnostic inspection of index usage, buffer hits, and execution times.
        """
        pool = custom_pool or await get_db_pool()
        query_embedding = await self.get_embedding(query)
        if query_embedding is None:
            return ["Failed to generate embedding for query."]

        target_model = model_name or settings.MODEL_NAME
        use_hnsw = is_pgvector_available() and len(query_embedding) == settings.SEMANTIC_CACHE_EMBEDDING_DIMENSION

        async with pool.connection() as conn:
            if use_hnsw:
                max_distance = max(0.0, 1.0 - self.similarity_threshold)
                vec_str = f"[{','.join(str(x) for x in query_embedding)}]"
                await conn.execute(f"SET LOCAL hnsw.ef_search = {settings.SEMANTIC_CACHE_HNSW_EF_SEARCH};")
                sql = """
                    EXPLAIN (ANALYZE, BUFFERS)
                    SELECT id, query_text, response_text, metadata, hit_count,
                           (1.0 - (embedding_vec <=> %s::vector)) AS similarity
                    FROM semantic_cache
                    WHERE user_id = %s
                      AND model_name = %s
                      AND embedding_model = %s
                      AND config_version = %s
                      AND expires_at > CURRENT_TIMESTAMP
                      AND (embedding_vec <=> %s::vector) <= %s
                    ORDER BY embedding_vec <=> %s::vector ASC
                    LIMIT 1
                """
                res = await conn.execute(
                    sql,
                    (
                        vec_str,
                        user_id,
                        target_model,
                        self.embedding_model,
                        self.config_version,
                        vec_str,
                        max_distance,
                        vec_str,
                    ),
                )
            else:
                sql = """
                    EXPLAIN (ANALYZE, BUFFERS)
                    SELECT id, query_text, response_text, metadata, hit_count,
                           cosine_similarity_array(embedding, %s) AS similarity
                    FROM semantic_cache
                    WHERE user_id = %s
                      AND model_name = %s
                      AND embedding_model = %s
                      AND config_version = %s
                      AND expires_at > CURRENT_TIMESTAMP
                    ORDER BY similarity DESC
                    LIMIT 1
                """
                res = await conn.execute(
                    sql,
                    (
                        query_embedding,
                        user_id,
                        target_model,
                        self.embedding_model,
                        self.config_version,
                    ),
                )
            rows = await res.fetchall()
            return [list(r.values())[0] for r in rows]

    async def invalidate(
        self,
        user_id: Optional[str] = None,
        query: Optional[str] = None,
        custom_pool: Optional[Any] = None,
    ) -> int:
        """
        Invalidates cache entries for a specific user, or for a specific query hash.
        """
        try:
            pool = custom_pool or await get_db_pool()
            async with pool.connection() as conn:
                if user_id and query:
                    qhash = compute_query_hash(query)
                    res = await conn.execute(
                        "DELETE FROM semantic_cache WHERE user_id = %s AND query_hash = %s",
                        (user_id, qhash),
                    )
                elif user_id:
                    res = await conn.execute(
                        "DELETE FROM semantic_cache WHERE user_id = %s",
                        (user_id,),
                    )
                else:
                    # Invalidate expired entries globally
                    res = await conn.execute(
                        "DELETE FROM semantic_cache WHERE expires_at <= CURRENT_TIMESTAMP"
                    )
                return res.rowcount
        except Exception as e:
            logger.exception(f"Error during cache invalidation: {e}")
            return 0


# Default global instance
semantic_cache = SemanticCacheService()
