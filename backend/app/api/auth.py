import os
import uuid
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
import httpx
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from backend.app.core.config import settings
from backend.app.core.database import get_db_pool
from backend.app.core.security import (
    AuthenticatedUser,
    get_current_user,
    hash_password,
    verify_password,
    generate_session_token,
    set_session_cookie,
    clear_session_cookie,
)
from backend.app.schemas.auth import (
    UserSignupRequest,
    UserLoginRequest,
    UserResponse,
    GoogleVerifyRequest,
)

logger = logging.getLogger("api_auth")
router = APIRouter(prefix="/auth", tags=["auth"])

SESSION_DURATION = timedelta(seconds=settings.SESSION_MAX_AGE_SECONDS)


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def signup(body: UserSignupRequest, request: Request, response: Response):
    pool = await get_db_pool()
    email = body.email.strip().lower()
    user_name = body.name.strip() if body.name else email.split("@")[0]

    async with pool.connection() as conn:
        res = await conn.execute("SELECT id FROM users WHERE email = %s", (email,))
        existing = await res.fetchone()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email address already exists. Please log in instead.",
            )

        pwd_hash = hash_password(body.password)
        user_id = str(uuid.uuid4())

        await conn.execute(
            """
            INSERT INTO users (id, email, password_hash, name, auth_provider)
            VALUES (%s, %s, %s, %s, 'local')
            """,
            (user_id, email, pwd_hash, user_name),
        )

        session_token = generate_session_token()
        now = datetime.now(timezone.utc)
        expires_at = now + SESSION_DURATION
        user_agent = request.headers.get("user-agent")
        ip_address = request.client.host if request.client else None

        await conn.execute(
            """
            INSERT INTO user_sessions (session_id, user_id, expires_at, created_at, user_agent, ip_address)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (session_token, user_id, expires_at, now, user_agent, ip_address),
        )

    set_session_cookie(response, session_token, max_age_seconds=int(SESSION_DURATION.total_seconds()))

    return UserResponse(
        id=user_id,
        email=email,
        name=user_name,
        auth_provider="local",
        created_at=now,
    )


@router.post("/login", response_model=UserResponse)
async def login(body: UserLoginRequest, request: Request, response: Response):
    pool = await get_db_pool()
    email = body.email.strip().lower()

    async with pool.connection() as conn:
        res = await conn.execute(
            "SELECT id, email, password_hash, name, avatar_url, auth_provider, created_at FROM users WHERE email = %s",
            (email,),
        )
        user_row = await res.fetchone()

        if not user_row:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        if not user_row.get("password_hash"):
            if user_row.get("auth_provider") == "google":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This account was registered using Google Sign-In. Please sign in with Google.",
                )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        if not verify_password(user_row["password_hash"], body.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        session_token = generate_session_token()
        now = datetime.now(timezone.utc)
        expires_at = now + SESSION_DURATION
        user_agent = request.headers.get("user-agent")
        ip_address = request.client.host if request.client else None

        await conn.execute(
            """
            INSERT INTO user_sessions (session_id, user_id, expires_at, created_at, user_agent, ip_address)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (session_token, user_row["id"], expires_at, now, user_agent, ip_address),
        )

    set_session_cookie(response, session_token, max_age_seconds=int(SESSION_DURATION.total_seconds()))

    return UserResponse(
        id=user_row["id"],
        email=user_row["email"],
        name=user_row["name"],
        avatar_url=user_row["avatar_url"],
        auth_provider=user_row["auth_provider"],
        created_at=user_row["created_at"],
    )


@router.post("/logout")
async def logout(request: Request, response: Response):
    session_token = request.cookies.get("session_token")
    if not session_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            session_token = auth_header[7:].strip()

    if session_token:
        pool = await get_db_pool()
        async with pool.connection() as conn:
            await conn.execute("DELETE FROM user_sessions WHERE session_id = %s", (session_token,))

    clear_session_cookie(response)
    return {"status": "ok", "message": "Successfully logged out"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: AuthenticatedUser = Depends(get_current_user)):
    return UserResponse(
        id=current_user.user_id,
        email=current_user.email,
        name=current_user.name,
        avatar_url=current_user.avatar_url,
        auth_provider=current_user.auth_provider,
    )


@router.post("/google/verify", response_model=UserResponse)
async def verify_google_token(body: GoogleVerifyRequest, request: Request, response: Response):
    client_id = settings.GOOGLE_CLIENT_ID
    id_info = None

    try:
        id_info = id_token.verify_oauth2_token(
            body.credential,
            google_requests.Request(),
            audience=client_id if client_id else None,
        )
    except Exception as e:
        logger.warning(f"Google token verification via id_token library failed: {e}")
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(
                    "https://oauth2.googleapis.com/tokeninfo",
                    params={"id_token": body.credential},
                    timeout=10.0,
                )
                if res.status_code == 200:
                    id_info = res.json()
                    if client_id and id_info.get("aud") != client_id:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Google ID token audience mismatch",
                        )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid Google ID token",
                    )
        except Exception as http_err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Google authentication failed: {http_err}",
            )

    if not id_info or not id_info.get("email"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google ID token did not contain an email address",
        )

    google_sub = id_info.get("sub")
    email = id_info.get("email").strip().lower()
    name = id_info.get("name") or email.split("@")[0]
    picture = id_info.get("picture")

    pool = await get_db_pool()
    now = datetime.now(timezone.utc)

    async with pool.connection() as conn:
        res = await conn.execute(
            "SELECT id, email, name, avatar_url, auth_provider FROM users WHERE google_id = %s OR email = %s",
            (google_sub, email),
        )
        user_row = await res.fetchone()

        if user_row:
            user_id = user_row["id"]
            await conn.execute(
                """
                UPDATE users
                SET google_id = %s,
                    name = COALESCE(%s, name),
                    avatar_url = COALESCE(%s, avatar_url),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (google_sub, name, picture, user_id),
            )
        else:
            user_id = str(uuid.uuid4())
            await conn.execute(
                """
                INSERT INTO users (id, email, name, avatar_url, auth_provider, google_id)
                VALUES (%s, %s, %s, %s, 'google', %s)
                """,
                (user_id, email, name, picture, google_sub),
            )

        session_token = generate_session_token()
        expires_at = now + SESSION_DURATION
        user_agent = request.headers.get("user-agent")
        ip_address = request.client.host if request.client else None

        await conn.execute(
            """
            INSERT INTO user_sessions (session_id, user_id, expires_at, created_at, user_agent, ip_address)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (session_token, user_id, expires_at, now, user_agent, ip_address),
        )

    set_session_cookie(response, session_token, max_age_seconds=int(SESSION_DURATION.total_seconds()))

    return UserResponse(
        id=user_id,
        email=email,
        name=name,
        avatar_url=picture,
        auth_provider="google",
        created_at=now,
    )


@router.get("/google/url")
async def get_google_auth_url(request: Request):
    client_id = settings.GOOGLE_CLIENT_ID
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google OAuth is not configured: GOOGLE_CLIENT_ID is missing in environment (.env).",
        )

    redirect_uri = settings.GOOGLE_REDIRECT_URI
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
    }
    url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return {"url": url}


@router.get("/google/callback")
async def google_auth_callback(code: str, request: Request):
    client_id = settings.GOOGLE_CLIENT_ID
    client_secret = settings.GOOGLE_CLIENT_SECRET
    frontend_url = settings.FRONTEND_URL
    redirect_uri = settings.GOOGLE_REDIRECT_URI

    if not client_id or not client_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth is missing client credentials on the server.",
        )

    async with httpx.AsyncClient() as client:
        token_res = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            headers={"Accept": "application/json"},
        )

        if token_res.status_code != 200:
            logger.error(f"Failed to exchange Google OAuth code: {token_res.text}")
            return RedirectResponse(url=f"{frontend_url}?auth_error=google_token_exchange_failed")

        token_data = token_res.json()
        access_token = token_data.get("access_token")

        user_res = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if user_res.status_code != 200:
            return RedirectResponse(url=f"{frontend_url}?auth_error=google_userinfo_failed")

        user_info = user_res.json()

    google_sub = user_info.get("sub")
    email = user_info.get("email", "").strip().lower()
    name = user_info.get("name") or email.split("@")[0]
    picture = user_info.get("picture")

    if not email:
        return RedirectResponse(url=f"{frontend_url}?auth_error=missing_email")

    pool = await get_db_pool()
    now = datetime.now(timezone.utc)
    session_token = generate_session_token()

    async with pool.connection() as conn:
        res = await conn.execute(
            "SELECT id FROM users WHERE google_id = %s OR email = %s",
            (google_sub, email),
        )
        user_row = await res.fetchone()

        if user_row:
            user_id = user_row["id"]
            await conn.execute(
                """
                UPDATE users
                SET google_id = %s,
                    name = COALESCE(%s, name),
                    avatar_url = COALESCE(%s, avatar_url),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (google_sub, name, picture, user_id),
            )
        else:
            user_id = str(uuid.uuid4())
            await conn.execute(
                """
                INSERT INTO users (id, email, name, avatar_url, auth_provider, google_id)
                VALUES (%s, %s, %s, %s, 'google', %s)
                """,
                (user_id, email, name, picture, google_sub),
            )

        expires_at = now + SESSION_DURATION
        user_agent = request.headers.get("user-agent")
        ip_address = request.client.host if request.client else None

        await conn.execute(
            """
            INSERT INTO user_sessions (session_id, user_id, expires_at, created_at, user_agent, ip_address)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (session_token, user_id, expires_at, now, user_agent, ip_address),
        )

    redirect = RedirectResponse(url=f"{frontend_url}?auth=success", status_code=status.HTTP_302_FOUND)
    set_session_cookie(redirect, session_token, max_age_seconds=int(SESSION_DURATION.total_seconds()))
    return redirect
