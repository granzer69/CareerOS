from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ExperienceLevelEnum


def test_get_my_profile_200(
    client: TestClient,
    db_session_mock: AsyncSession,
    current_user_id: UUID,
) -> None:
    """GET /user-profile/me returns the caller's profile."""
    profile = SimpleNamespace(
        id=UUID("00000000-0000-0000-0000-000000000123"),
        user_id=current_user_id,
        skills=["python"],
        target_role="Backend Engineer",
        experience_level=ExperienceLevelEnum.STUDENT,
        created_at=datetime.now(timezone.utc),
    )
    db_session_mock.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda: profile)

    response = client.get("/user-profile/me")

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == str(current_user_id)
    assert body["target_role"] == "Backend Engineer"


def test_get_my_profile_404_when_missing(
    client: TestClient,
    db_session_mock: AsyncSession,
) -> None:
    """GET /user-profile/me returns not_found when the profile was never created."""
    db_session_mock.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda: None)

    response = client.get("/user-profile/me")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "not_found"
