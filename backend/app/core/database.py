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
        logger.info("Database schemas verified and initialized.")


async def get_db_pool() -> AsyncConnectionPool:
    """Returns the opened connection pool, initializing if closed."""
    if pool.closed:
        await pool.open()
    return pool
