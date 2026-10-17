import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())


class Settings:
    # Project Info
    PROJECT_NAME: str = "LangGraph Chatbot Web API"
    VERSION: str = "1.0.0"

    # Database
    POSTGRES_URI: str = os.getenv(
        "POSTGRES_URI",
        "postgresql://postgres:postgres@localhost:5432/langgraph",
    )
    DB_POOL_MAX_SIZE: int = int(os.getenv("DB_POOL_MAX_SIZE", "20"))

    # OpenAI & LLM
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    MODEL_NAME: str = os.getenv("MODEL", "gpt-5.4-mini")

    # CORS & Frontend
    ALLOWED_ORIGINS: list[str] = [
        o.strip()
        for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
        if o.strip()
    ]
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")

    # Security & Cookies
    COOKIE_SECURE: bool = os.getenv("COOKIE_SECURE", "false").lower() in ("true", "1", "yes")
    COOKIE_SAMESITE: str = os.getenv("COOKIE_SAMESITE", "lax").lower()
    SESSION_MAX_AGE_SECONDS: int = 7 * 24 * 3600  # 7 days
    ALLOW_DEV_AUTH_BYPASS: bool = os.getenv("ALLOW_DEV_AUTH_BYPASS", "false").lower() in ("true", "1")

    # Google OAuth
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    GOOGLE_REDIRECT_URI: str = os.getenv(
        "GOOGLE_REDIRECT_URI",
        "http://127.0.0.1:8000/api/auth/google/callback",
    )

    # LangGraph Short-Term Memory
    SUMMARY_TRIGGER: int = int(os.getenv("SUMMARY_TRIGGER", "12"))

    # Semantic Cache Settings
    SEMANTIC_CACHE_ENABLED: bool = os.getenv("SEMANTIC_CACHE_ENABLED", "true").lower() in ("true", "1", "yes")
    SEMANTIC_CACHE_SIMILARITY_THRESHOLD: float = float(os.getenv("SEMANTIC_CACHE_SIMILARITY_THRESHOLD", "0.88"))
    SEMANTIC_CACHE_TTL_SECONDS: int = int(os.getenv("SEMANTIC_CACHE_TTL_SECONDS", "86400"))  # 24 hours default
    SEMANTIC_CACHE_EMBEDDING_MODEL: str = os.getenv("SEMANTIC_CACHE_EMBEDDING_MODEL", "text-embedding-3-small")
    SEMANTIC_CACHE_MAX_ENTRIES_PER_USER: int = int(os.getenv("SEMANTIC_CACHE_MAX_ENTRIES_PER_USER", "500"))
    SEMANTIC_CACHE_CONFIG_VERSION: str = os.getenv("SEMANTIC_CACHE_CONFIG_VERSION", "v1")


settings = Settings()

