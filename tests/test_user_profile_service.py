from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ExperienceLevelEnum
from app.services.user_profile_service import (
    UserProfileForbiddenError,
    UserProfileInvalidOperationError,
    UserProfileNotFoundError,
    UserProfileService,
)
from app.schemas.user_profile import UserProfileCreate, UserProfileUpdate


@pytest.mark.asyncio
async def test_upsert_forbidden_when_modifying_other_user(
    db_session_mock: AsyncSession,
    current_user_id: UUID,
    other_user_id: UUID,
) -> None:
    """Reject when current user tries to modify someone else's profile."""
    service = UserProfileService(db_session=db_session_mock)

    payload = UserProfileUpdate(skills=["python"])
    with pytest.raises(UserProfileForbiddenError) as exc:
        await service.upsert_user_profile(
            current_user_id=current_user_id,
            user_id=other_user_id,
            payload=payload,
        )

    assert exc.value.code == "forbidden"
    db_session_mock.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_upsert_create_rejects_user_id_mismatch(
    db_session_mock: AsyncSession,
    current_user_id: UUID,
) -> None:
    """Reject create when path user_id and payload.user_id differ."""
    service = UserProfileService(db_session=db_session_mock)

    # No existing profile
    db_session_mock.execute.return_value = SimpleNamespace(
        scalar_one_or_none=lambda: None
    )

    payload = UserProfileCreate(
        user_id=UUID("00000000-0000-0000-0000-000000000099"),
        skills=["python"],
        target_role="Backend Engineer",
        experience_level=ExperienceLevelEnum.JUNIOR,
    )
    with pytest.raises(UserProfileInvalidOperationError) as exc:
        await service.upsert_user_profile(
            current_user_id=current_user_id,
            user_id=current_user_id,
            payload=payload,
        )

    assert exc.value.code == "user_id_mismatch"
    db_session_mock.rollback.assert_awaited()


@pytest.mark.asyncio
async def test_upsert_update_not_found_when_profile_missing(
    db_session_mock: AsyncSession,
    current_user_id: UUID,
) -> None:
    """Return not_found when updating a non-existent profile."""
    service = UserProfileService(db_session=db_session_mock)

    db_session_mock.execute.return_value = SimpleNamespace(
        scalar_one_or_none=lambda: None
    )

    payload = UserProfileUpdate(target_role="Data Scientist")
    with pytest.raises(UserProfileNotFoundError) as exc:
        await service.upsert_user_profile(
            current_user_id=current_user_id,
            user_id=current_user_id,
            payload=payload,
        )

    assert exc.value.code == "not_found"
    db_session_mock.rollback.assert_awaited()


@pytest.mark.asyncio
async def test_upsert_create_happy_path_persists_profile(
    db_session_mock: AsyncSession,
    current_user_id: UUID,
) -> None:
    """Create a new profile when none exists and return the saved model."""
    service = UserProfileService(db_session=db_session_mock)

    db_session_mock.execute.return_value = SimpleNamespace(
        scalar_one_or_none=lambda: None
    )

    payload = UserProfileCreate(
        user_id=current_user_id,
        skills=["python", "fastapi"],
        target_role="Backend Engineer",
        experience_level=ExperienceLevelEnum.MID,
    )

    # Refresh will be called with the ORM instance; return data via attribute access.
    async def _refresh(obj: object) -> None:
        setattr(obj, "id", UUID("00000000-0000-0000-0000-000000000123"))

    db_session_mock.refresh.side_effect = _refresh

    result = await service.upsert_user_profile(
        current_user_id=current_user_id,
        user_id=current_user_id,
        payload=payload,
    )

    assert result.user_id == current_user_id
    assert result.skills == ["python", "fastapi"]
    assert result.target_role == "Backend Engineer"
    assert result.experience_level == ExperienceLevelEnum.MID
    db_session_mock.commit.assert_awaited()


@pytest.mark.asyncio
async def test_upsert_rolls_back_on_db_error(
    db_session_mock: AsyncSession,
    current_user_id: UUID,
) -> None:
    """Rollback and re-raise when the DB layer raises an exception."""
    service = UserProfileService(db_session=db_session_mock)

    db_session_mock.execute.side_effect = RuntimeError("db down")

    payload = UserProfileUpdate(skills=["x"])
    with pytest.raises(RuntimeError):
        await service.upsert_user_profile(
            current_user_id=current_user_id,
            user_id=current_user_id,
            payload=payload,
        )

    db_session_mock.rollback.assert_awaited()

