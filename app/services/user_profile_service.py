from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.models.user_profile import UserProfile
from app.schemas.user_profile import (
    UserProfileCreate,
    UserProfileRead,
    UserProfileUpdate,
)


class UserProfileInvalidOperationError(DomainError):
    """Raised when profile payload/path are inconsistent."""


class UserProfileForbiddenError(DomainError):
    """Raised when a user attempts to modify another user's profile."""


class UserProfileNotFoundError(DomainError):
    """Raised when a user profile does not exist for the given user_id."""


class UserProfileService:
    def __init__(self, db_session: AsyncSession) -> None:
        self._db_session = db_session

    async def upsert_user_profile(
        self,
        *,
        current_user_id: UUID,
        user_id: UUID,
        payload: UserProfileCreate | UserProfileUpdate,
    ) -> UserProfileRead:
        """
        Create or update the authenticated user's profile.

        Enforces that a user may only modify their own profile and that create payloads
        are consistent with the path user_id.
        """
        try:
            if current_user_id != user_id:
                raise UserProfileForbiddenError(
                    detail="Not allowed to modify another user's profile",
                    code="forbidden",
                    http_status=403,
                )

            stmt = select(UserProfile).where(UserProfile.user_id == user_id)
            result = await self._db_session.execute(stmt)
            existing: UserProfile | None = result.scalar_one_or_none()

            if existing is None:
                if isinstance(payload, UserProfileUpdate):
                    raise UserProfileNotFoundError(
                        detail="User profile does not exist for this user_id",
                        code="not_found",
                        http_status=404,
                    )
                if payload.user_id != user_id:
                    raise UserProfileInvalidOperationError(
                        detail="Path user_id does not match payload user_id",
                        code="user_id_mismatch",
                        http_status=400,
                    )
                created_at = datetime.now(timezone.utc)
                profile = UserProfile(
                    user_id=user_id,
                    skills=list(payload.skills or []),
                    target_role=payload.target_role,
                    experience_level=payload.experience_level,
                    created_at=created_at,
                )
                self._db_session.add(profile)
            else:
                update_data: dict[str, Any] = payload.model_dump(
                    exclude_unset=True
                )
                if "skills" in update_data and update_data["skills"] is not None:
                    existing.skills = list(update_data["skills"])
                if (
                    "target_role" in update_data
                    and update_data["target_role"] is not None
                ):
                    existing.target_role = update_data["target_role"]
                if (
                    "experience_level" in update_data
                    and update_data["experience_level"] is not None
                ):
                    existing.experience_level = update_data["experience_level"]
                profile = existing

            await self._db_session.commit()
            await self._db_session.refresh(profile)
            return UserProfileRead.model_validate(profile)
        except Exception as exc:
            await self._db_session.rollback()
            raise

