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
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_semantic_cache_lookup ON semantic_cache(user_id, model_name, config_version, expires_at);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_semantic_cache_query_hash ON semantic_cache(user_id, query_hash, expires_at);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_semantic_cache_expires ON semantic_cache(expires_at);")

        # 6. Cosine Similarity PL/pgSQL Function for vector arrays
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
        logger.info("Database schemas verified and initialized.")



async def get_db_pool() -> AsyncConnectionPool:
    """Returns the opened connection pool, initializing if closed."""
    if pool.closed:
        await pool.open()
    return pool
