import sys
import os
from pathlib import Path

# Ensure 'lamit' directory is on sys.path regardless of execution CWD
_lamit_dir = str(Path(__file__).resolve().parent.parent.parent)
if _lamit_dir not in sys.path:
    sys.path.insert(0, _lamit_dir)

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Policy on Windows before async database initialization
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

from backend.app.core.config import settings
from backend.app.core.database import pool, get_db_pool
from backend.app.graph.engine import ensure_initialized
from backend.app.api.router import api_router

logger = logging.getLogger("backend")
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database connection pool and LangGraph engine...")
    bot = await ensure_initialized()
    app.state.pool = pool
    app.state.chatbot = bot
    logger.info("LangGraph engine and PostgreSQL pool initialized successfully.")
    yield
    logger.info("Closing database connection pool...")
    if not pool.closed:
        await pool.close()
    logger.info("Shutdown complete.")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description="Production-ready FastAPI + LangGraph AI Chatbot Backend",
        version=settings.VERSION,
        lifespan=lifespan,
    )

    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Global Exception Handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.exception(f"Unhandled server error at {request.method} {request.url.path}: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An internal server error occurred. Please try again later."},
        )

    # Mount unified API router (/api/auth, /api/threads, /api/chat, /api/history)
    app.include_router(api_router)

    # Health Check Endpoint
    @app.get("/health", tags=["health"])
    async def health_check():
        db_healthy = False
        try:
            if pool and not pool.closed:
                async with pool.connection() as conn:
                    await conn.execute("SELECT 1")
                    db_healthy = True
        except Exception:
            db_healthy = False

        return {
            "status": "ok" if db_healthy else "degraded",
            "service": settings.PROJECT_NAME,
            "database": "connected" if db_healthy else "disconnected",
        }

    return app


app = create_app()


def main():
    import selectors
    import uvicorn

    def loop_factory():
        return asyncio.SelectorEventLoop(selectors.SelectSelector())

    config = uvicorn.Config(
        "backend.app.main:app",
        host="127.0.0.1",
        port=8000,
        loop="none",
        reload=False,
    )
    server = uvicorn.Server(config)
    asyncio.run(server.serve(), loop_factory=loop_factory)


if __name__ == "__main__":
    main()
