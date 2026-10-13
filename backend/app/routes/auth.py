"""Authentication and Token Usage routes for DocChat AI.

All database access uses raw psycopg2 SQL queries (no ORM).
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from psycopg2.extensions import connection as PgConn

from app.db.database import get_conn
from app.schemas import (
    UserRegisterRequest,
    UserLoginRequest,
    TokenResponse,
    UserInfo,
    UsageSummaryResponse,
)
from app.services.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    get_required_user,
)
from app.services.usage import get_usage_summary

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Authentication & Usage"])


@router.post("/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@router.post("/api/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: UserRegisterRequest, conn: PgConn = Depends(get_conn)):
    """Register a new user account and return a JWT access token."""
    clean_username = payload.username.strip()
    clean_email = payload.email.strip() if payload.email else None

    # Check for existing username
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM users WHERE LOWER(username) = LOWER(%s) LIMIT 1",
            (clean_username,),
        )
        if cur.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Username '{clean_username}' is already registered. Please choose another.",
            )

    # Check for existing email if provided
    if clean_email:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM users WHERE LOWER(email) = LOWER(%s) LIMIT 1",
                (clean_email,),
            )
            if cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Email '{clean_email}' is already associated with an account.",
                )

    # Insert new user
    hashed = hash_password(payload.password)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO users (username, email, hashed_password, is_active)
            VALUES (%s, %s, %s, TRUE)
            RETURNING id, username, email, is_active
            """,
            (clean_username, clean_email, hashed),
        )
        new_user = cur.fetchone()
    conn.commit()

    logger.info(f"[Auth] Registered new user: '{clean_username}' (id={new_user['id']}).")

    access_token = create_access_token(
        data={"sub": new_user["username"], "user_id": new_user["id"]}
    )
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserInfo(
            id=new_user["id"],
            username=new_user["username"],
            email=new_user["email"],
            is_active=new_user["is_active"],
        ),
    )


@router.post("/auth/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
@router.post("/api/auth/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def login(payload: UserLoginRequest, conn: PgConn = Depends(get_conn)):
    """Authenticate with username/email and password to obtain a JWT access token."""
    login_id = payload.username.strip()

    # Allow login by username or email
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, username, email, hashed_password, is_active
            FROM users
            WHERE LOWER(username) = LOWER(%s) OR LOWER(email) = LOWER(%s)
            LIMIT 1
            """,
            (login_id, login_id),
        )
        user = cur.fetchone()

    if not user or not verify_password(payload.password, user["hashed_password"]):
        logger.warning(f"[Auth] Failed login attempt for '{login_id}'.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account has been deactivated.",
        )

    logger.info(f"[Auth] User '{user['username']}' (id={user['id']}) logged in.")

    access_token = create_access_token(
        data={"sub": user["username"], "user_id": user["id"]}
    )
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserInfo(
            id=user["id"],
            username=user["username"],
            email=user["email"],
            is_active=user["is_active"],
        ),
    )


@router.get("/auth/me", response_model=UserInfo, status_code=status.HTTP_200_OK)
@router.get("/api/auth/me", response_model=UserInfo, status_code=status.HTTP_200_OK)
async def get_me(current_user: dict = Depends(get_required_user)):
    """Retrieve the profile information for the authenticated user."""
    return UserInfo(
        id=current_user["id"],
        username=current_user["username"],
        email=current_user["email"],
        is_active=current_user["is_active"],
    )


@router.get("/usage", response_model=UsageSummaryResponse, status_code=status.HTTP_200_OK)
@router.get("/api/usage", response_model=UsageSummaryResponse, status_code=status.HTTP_200_OK)
async def get_usage(
    current_user: dict = Depends(get_current_user),
    conn: PgConn = Depends(get_conn),
):
    """Retrieve token usage metrics and estimated costs for the user."""
    summary = get_usage_summary(conn, user_id=current_user["id"])
    return summary
