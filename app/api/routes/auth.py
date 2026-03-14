from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import create_access_token
from app.core.database import get_db_session
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])

PBKDF2_ITERATIONS = 600_000


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: UUID


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def _verify_password(password: str, hashed_password: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = hashed_password.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations),
        )
        return hmac.compare_digest(candidate.hex(), digest_hex)
    except (TypeError, ValueError):
        return False


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    payload: RegisterRequest,
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TokenResponse:
    """Register a new user and return a JWT access token."""
    existing = await db_session.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"detail": "Email already registered", "code": "email_exists"},
        )

    user = User(email=payload.email, hashed_password=_hash_password(payload.password))
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    return TokenResponse(
        access_token=create_access_token(user_id=user.id),
        user_id=user.id,
    )


@router.post("/login", response_model=TokenResponse)
async def login_user(
    payload: LoginRequest,
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TokenResponse:
    """Authenticate a user and return a JWT access token."""
    result = await db_session.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if user is None or not _verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "Invalid email or password", "code": "invalid_credentials"},
        )

    return TokenResponse(
        access_token=create_access_token(user_id=user.id),
        user_id=user.id,
    )
