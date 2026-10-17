import logging
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row

from backend.app.core.config import settings

logger = logging.getLogger("database")

connection_kwargs = {
    "autocommit": True,
    "prepare_threshold": 0,
    "row_factory": dict_row,
}

pool = AsyncConnectionPool(
    conninfo=settings.POSTGRES_URI,
    max_size=settings.DB_POOL_MAX_SIZE,
    kwargs=connection_kwargs,
    open=False,
)


async def setup_database_tables():
    """
    Idempotent schema initialization for PostgreSQL.
    Ensures users, user_sessions, chat_threads, and chat_messages exist.
    """
    async with pool.connection() as conn:
        # 1. Users table
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            TEXT PRIMARY KEY,
                email         TEXT UNIQUE NOT NULL,
                password_hash TEXT,
                name          TEXT,
                avatar_url    TEXT,
                auth_provider TEXT NOT NULL DEFAULT 'local',
                google_id     TEXT,
                created_at    TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                updated_at    TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url TEXT;")
        await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_provider TEXT NOT NULL DEFAULT 'local';")
        await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS google_id TEXT;")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id);")

        # 2. User sessions table
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_sessions (
                session_id  TEXT PRIMARY KEY,
                user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires_at  TIMESTAMPTZ NOT NULL,
                created_at  TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                user_agent  TEXT,
                ip_address  TEXT
            );
            """
        )
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_sessions_user ON user_sessions(user_id);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_sessions_expires ON user_sessions(expires_at);")

        # 3. Chat threads table with multi-tenant user isolation
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_threads (
                thread_id  TEXT PRIMARY KEY,
                user_id    TEXT NOT NULL DEFAULT 'default_user',
                title      TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        await conn.execute("ALTER TABLE chat_threads ADD COLUMN IF NOT EXISTS user_id TEXT NOT NULL DEFAULT 'default_user';")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_threads_user ON chat_threads(user_id, updated_at DESC);")

        # 4. Chat messages display truth table
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_messages (
                id          BIGSERIAL PRIMARY KEY,
                thread_id   TEXT        NOT NULL,
                role        TEXT        NOT NULL,
                content     TEXT        NOT NULL,
                tool_name   TEXT,
                created_at  TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_thread ON chat_messages(thread_id, id);")

        # 5. Semantic Cache table and indexes
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS semantic_cache (
                id                  BIGSERIAL PRIMARY KEY,
                user_id             TEXT NOT NULL,
                scope               TEXT NOT NULL DEFAULT 'private',
                query_text          TEXT NOT NULL,
                query_hash          TEXT NOT NULL,
                embedding           DOUBLE PRECISION[] NOT NULL,
                response_text       TEXT NOT NULL,
                model_name          TEXT NOT NULL,
                embedding_model     TEXT NOT NULL,
                config_version      TEXT NOT NULL DEFAULT 'v1',
                metadata            JSONB DEFAULT '{}'::jsonb,
                hit_count           INTEGER NOT NULL DEFAULT 0,
                last_accessed_at    TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                created_at          TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                expires_at          TIMESTAMPTZ NOT NULL
            );
            """
        )
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_semantic_cache_lookup ON semantic_cache(user_id, model_name, embedding_model, config_version, expires_at);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_semantic_cache_query_hash ON semantic_cache(user_id, query_hash, expires_at);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_semantic_cache_expires ON semantic_cache(expires_at);")

        # 6. Cosine Similarity PL/pgSQL Function for vector arrays (fallback / dual-mode)
        await conn.execute(
            """
            CREATE OR REPLACE FUNCTION cosine_similarity_array(a DOUBLE PRECISION[], b DOUBLE PRECISION[])
            RETURNS DOUBLE PRECISION AS $$
            DECLARE
                dot_product DOUBLE PRECISION := 0;
                norm_a DOUBLE PRECISION := 0;
                norm_b DOUBLE PRECISION := 0;
                i INTEGER;
                dim INTEGER;
            BEGIN
                dim := array_length(a, 1);
                IF dim IS NULL OR dim <> array_length(b, 1) THEN
                    RETURN 0.0;
                END IF;
                FOR i IN 1..dim LOOP
                    dot_product := dot_product + (a[i] * b[i]);
                    norm_a := norm_a + (a[i] * a[i]);
                    norm_b := norm_b + (b[i] * b[i]);
                END LOOP;
                IF norm_a <= 0.0 OR norm_b <= 0.0 THEN
                    RETURN 0.0;
                END IF;
                RETURN dot_product / (sqrt(norm_a) * sqrt(norm_b));
            END;
            $$ LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE;
            """
        )

        # 7. Check pgvector extension and configure HNSW index
        global _pgvector_active, _has_iterative_scan
        if not settings.SEMANTIC_CACHE_FORCE_ARRAY_FALLBACK:
            _pgvector_active = await probe_pgvector_support(conn)
        else:
            _pgvector_active = False
            logger.info("Semantic cache pgvector explicitly disabled by SEMANTIC_CACHE_FORCE_ARRAY_FALLBACK.")

        if _pgvector_active:
            dim = settings.SEMANTIC_CACHE_EMBEDDING_DIMENSION
            m = settings.SEMANTIC_CACHE_HNSW_M
            ef_c = settings.SEMANTIC_CACHE_HNSW_EF_CONSTRUCTION

            # Add vector column if missing
            await conn.execute(f"ALTER TABLE semantic_cache ADD COLUMN IF NOT EXISTS embedding_vec vector({dim});")

            # Backfill vector column from array representation for any existing records
            await conn.execute(
                """
                UPDATE semantic_cache
                SET embedding_vec = embedding::text::vector
                WHERE embedding_vec IS NULL AND embedding IS NOT NULL;
                """
            )

            # Create HNSW index using vector_cosine_ops
            await conn.execute(
                f"""
                CREATE INDEX IF NOT EXISTS idx_semantic_cache_hnsw
                ON semantic_cache
                USING hnsw (embedding_vec vector_cosine_ops)
                WITH (m = {m}, ef_construction = {ef_c});
                """
            )

            # Check whether iterative index scan is supported by this pgvector build (pgvector >= 0.7.0)
            try:
                res_scan = await conn.execute("SELECT 1 FROM pg_settings WHERE name = 'hnsw.iterative_scan';")
                _has_iterative_scan = (await res_scan.fetchone()) is not None
            except Exception:
                _has_iterative_scan = False

            logger.info(
                f"pgvector HNSW index initialized successfully (dim={dim}, m={m}, ef_construction={ef_c}, "
                f"iterative_scan={_has_iterative_scan})."
            )
        else:
            logger.warning(
                "pgvector extension is not available in PostgreSQL. Operating in resilient array fallback "
                "mode with pre-filtered B-tree indexes and PL/pgSQL cosine similarity."
            )

        logger.info("Database schemas verified and initialized.")


_pgvector_active: bool = False
_has_iterative_scan: bool = False


async def probe_pgvector_support(conn) -> bool:
    """
    Checks if pgvector extension is available in PostgreSQL and enables it if present.
    """
    try:
        res = await conn.execute("SELECT 1 FROM pg_available_extensions WHERE name = 'vector';")
        available = await res.fetchone()
        if not available:
            return False

        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        res_test = await conn.execute("SELECT '[1,2,3]'::vector;")
        return res_test is not None
    except Exception as e:
        logger.warning(f"pgvector probe check encountered exception: {e}")
        return False


def is_pgvector_available() -> bool:
    """Returns True if pgvector extension and HNSW are active."""
    return _pgvector_active


def has_iterative_scan_support() -> bool:
    """Returns True if hnsw.iterative_scan is supported."""
    return _has_iterative_scan


def get_pgvector_status() -> dict:
    """Returns complete diagnostic status of pgvector and HNSW configuration."""
    return {
        "pgvector_active": _pgvector_active,
        "has_iterative_scan": _has_iterative_scan,
        "embedding_dimension": settings.SEMANTIC_CACHE_EMBEDDING_DIMENSION,
        "hnsw_m": settings.SEMANTIC_CACHE_HNSW_M,
        "hnsw_ef_construction": settings.SEMANTIC_CACHE_HNSW_EF_CONSTRUCTION,
        "hnsw_ef_search": settings.SEMANTIC_CACHE_HNSW_EF_SEARCH,
        "similarity_threshold": settings.SEMANTIC_CACHE_SIMILARITY_THRESHOLD,
    }


async def get_db_pool() -> AsyncConnectionPool:
    """Returns the opened connection pool, initializing if closed."""
    if pool.closed:
        await pool.open()
    return pool
