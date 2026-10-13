"""Authentication and security services — JWT validation, password hashing, user lookup.

All database access uses raw psycopg2 SQL queries (no ORM).
"""

from datetime import datetime, timedelta, timezone
import logging
from typing import Optional, Any

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import settings
from app.db.database import get_conn

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Generate a signed JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT access token."""
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token signature has expired.")
        return None
    except (jwt.PyJWTError, Exception) as e:
        logger.warning(f"JWT decode error: {e}")
        return None


# ---------------------------------------------------------------------------
# User DB helpers (raw SQL)
# ---------------------------------------------------------------------------

def _fetch_user_by_username(conn: Any, username: str) -> Optional[dict]:
    """Return a user row dict by username (case-insensitive), or None."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, username, email, hashed_password, is_active, created_at "
            "FROM users WHERE LOWER(username) = LOWER(%s) LIMIT 1",
            (username,),
        )
        return cur.fetchone()


def _fetch_user_by_id(conn: Any, user_id: int) -> Optional[dict]:
    """Return a user row dict by primary key, or None."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, username, email, hashed_password, is_active, created_at "
            "FROM users WHERE id = %s LIMIT 1",
            (user_id,),
        )
        return cur.fetchone()


def get_or_create_guest_user(conn: Any) -> dict:
    """Retrieve or create the default guest user for backwards-compatible test calls."""
    user = _fetch_user_by_username(conn, "guest")
    if not user:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (username, email, hashed_password, is_active)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (username) DO NOTHING
                RETURNING id, username, email, hashed_password, is_active, created_at
                """,
                ("guest", "guest@docchat.local", hash_password("guestpassword123"), True),
            )
            user = cur.fetchone()
        conn.commit()
        if not user:
            # ON CONFLICT path — fetch the existing row
            user = _fetch_user_by_username(conn, "guest")
    return user


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    conn: Any = Depends(get_conn),
) -> dict:
    """FastAPI dependency to extract and authenticate the current user.

    - Valid JWT Bearer → returns the authenticated user dict.
    - No token + REQUIRE_AUTH=True → raises HTTP 401.
    - No token + REQUIRE_AUTH=False → falls back to guest user.
    """
    if credentials and credentials.credentials:
        token = credentials.credentials
        payload = decode_access_token(token)
        if not payload or "sub" not in payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired authentication credentials.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        username = payload.get("sub")
        user = _fetch_user_by_username(conn, username)
        if not user or not user["is_active"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account does not exist or has been disabled.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user

    if settings.REQUIRE_AUTH:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is required for this action.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return get_or_create_guest_user(conn)


def get_required_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    conn: Any = Depends(get_conn),
) -> dict:
    """FastAPI dependency that strictly requires a valid JWT token."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    username = payload.get("sub")
    user = _fetch_user_by_username(conn, username)
    if not user or not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account does not exist or has been disabled.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
