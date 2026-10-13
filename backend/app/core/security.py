import secrets
from datetime import datetime, timezone
from typing import Optional
from fastapi import HTTPException, Request, Response, status
import argon2

from backend.app.core.config import settings

# Argon2 Password Hasher (OWASP recommended parameters)
_pwd_hasher = argon2.PasswordHasher(
    time_cost=2,
    memory_cost=19456,  # 19 MiB
    parallelism=1,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    """Securely hash a password using Argon2id."""
    return _pwd_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Verify a plain password against an Argon2 hash."""
    if not password_hash:
        return False
    try:
        return _pwd_hasher.verify(password_hash, password)
    except Exception:
        return False


def generate_session_token() -> str:
    """Generate a high-entropy URL-safe session token."""
    return secrets.token_urlsafe(32)


def set_session_cookie(
    response: Response,
    session_id: str,
    max_age_seconds: Optional[int] = None,
):
    """Sets a secure HTTP-only session cookie on the response."""
    max_age = max_age_seconds or settings.SESSION_MAX_AGE_SECONDS
    response.set_cookie(
        key="session_token",
        value=session_id,
        httponly=True,
        max_age=max_age,
        expires=max_age,
        samesite=settings.COOKIE_SAMESITE,
        secure=settings.COOKIE_SECURE,
        path="/",
    )


def clear_session_cookie(response: Response):
    """Clears the session cookie on the response."""
    response.delete_cookie(
        key="session_token",
        path="/",
    )


class AuthenticatedUser:
    def __init__(
        self,
        user_id: str,
        email: str,
        name: Optional[str] = None,
        avatar_url: Optional[str] = None,
        auth_provider: str = "local",
        is_authenticated: bool = True,
    ):
        self.user_id = user_id
        self.email = email
        self.name = name
        self.avatar_url = avatar_url
        self.auth_provider = auth_provider
        self.is_authenticated = is_authenticated


async def get_current_user(request: Request) -> AuthenticatedUser:
    """
    FastAPI dependency for strict PostgreSQL session-based authentication.
    Validates HTTP-only cookie 'session_token' or 'Authorization: Bearer <token>'.
    Ensures session has not expired and fetches the authenticated user.
    """
    # 1. Check HTTP-only cookie
    session_token = request.cookies.get("session_token")

    # 2. Check Bearer authorization header fallback
    if not session_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            session_token = auth_header[7:].strip()

    # 3. Development / Test bypass header (only active if explicitly allowed by environment)
    if not session_token:
        if settings.ALLOW_DEV_AUTH_BYPASS:
            x_user_id = request.headers.get("X-User-Id")
            if x_user_id and x_user_id.strip():
                uid = x_user_id.strip()
                return AuthenticatedUser(
                    user_id=uid,
                    email=f"{uid}@local.app",
                    name=uid,
                )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please sign in.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 4. Lookup session in PostgreSQL
    pool = getattr(request.app.state, "pool", None)
    if pool is None:
        from backend.app.core.database import get_db_pool
        pool = await get_db_pool()

    async with pool.connection() as conn:
        res = await conn.execute(
            """
            SELECT s.session_id, s.user_id, s.expires_at,
                   u.email, u.name, u.avatar_url, u.auth_provider
            FROM user_sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.session_id = %s AND s.expires_at > CURRENT_TIMESTAMP
            """,
            (session_token,),
        )
        row = await res.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session. Please sign in again.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return AuthenticatedUser(
            user_id=row["user_id"],
            email=row["email"],
            name=row["name"],
            avatar_url=row["avatar_url"],
            auth_provider=row["auth_provider"],
        )


async def verify_thread_ownership(conn, thread_id: str, user_id: str) -> dict:
    """
    Verifies that the requested thread exists and belongs to the authenticated user.
    Raises 404 if not found, 403 if belonging to a different user.
    """
    result = await conn.execute(
        "SELECT thread_id, user_id, title FROM chat_threads WHERE thread_id = %s",
        (thread_id,),
    )
    thread = await result.fetchone()
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread not found",
        )

    thread_owner = thread.get("user_id")
    if thread_owner and thread_owner != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You do not have permission to access this conversation.",
        )

    return thread
