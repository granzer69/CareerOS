from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ExperienceLevelEnum


def test_create_user_profile_201_happy_path(
    client: TestClient,
    db_session_mock: AsyncSession,
    current_user_id: UUID,
) -> None:
    """Create profile returns 201 and response schema."""
    db_session_mock.execute.return_value = SimpleNamespace(
        scalar_one_or_none=lambda: None
    )

    async def _refresh(obj: object) -> None:
        setattr(obj, "id", UUID("00000000-0000-0000-0000-000000000123"))

    db_session_mock.refresh.side_effect = _refresh

    resp = client.post(
        f"/user-profile/{current_user_id}",
        json={
            "user_id": str(current_user_id),
            "skills": ["python"],
            "target_role": "Backend Engineer",
            "experience_level": ExperienceLevelEnum.JUNIOR.value,
        },
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["user_id"] == str(current_user_id)
    assert body["skills"] == ["python"]
    assert body["target_role"] == "Backend Engineer"
    assert body["experience_level"] == ExperienceLevelEnum.JUNIOR.value
    assert "created_at" in body


def test_create_user_profile_400_user_id_mismatch(
    client: TestClient,
    db_session_mock: AsyncSession,
    current_user_id: UUID,
) -> None:
    """Create profile returns 400 with {detail, code} when user_id mismatches."""
    db_session_mock.execute.return_value = SimpleNamespace(
        scalar_one_or_none=lambda: None
    )

    resp = client.post(
        f"/user-profile/{current_user_id}",
        json={
            "user_id": "00000000-0000-0000-0000-000000000099",
            "skills": ["python"],
            "target_role": "Backend Engineer",
            "experience_level": ExperienceLevelEnum.STUDENT.value,
        },
    )

    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert detail["code"] == "user_id_mismatch"
    assert "detail" in detail


def test_update_user_profile_404_when_missing(
    client: TestClient,
    db_session_mock: AsyncSession,
    current_user_id: UUID,
) -> None:
    """Update profile returns 404 with {detail, code} when profile missing."""
    db_session_mock.execute.return_value = SimpleNamespace(
        scalar_one_or_none=lambda: None
    )

    resp = client.put(
        f"/user-profile/{current_user_id}",
        json={"target_role": "Data Scientist"},
    )

    assert resp.status_code == 404
    detail = resp.json()["detail"]
    assert detail["code"] == "not_found"


def test_update_user_profile_403_when_other_user(
    fastapi_app: FastAPI,
    db_session_mock: AsyncSession,
    current_user_id: UUID,
    other_user_id: UUID,
) -> None:
    """Update profile returns 403 with {detail, code} when modifying another user."""
    # Override auth to return current_user_id, then call other_user_id path.
    with TestClient(fastapi_app) as client:
        resp = client.put(
            f"/user-profile/{other_user_id}",
            json={"skills": ["x"]},
        )

    assert resp.status_code == 403
    detail = resp.json()["detail"]
    assert detail["code"] == "forbidden"


def test_update_user_profile_500_internal_error_shape(
    client: TestClient,
    db_session_mock: AsyncSession,
    current_user_id: UUID,
) -> None:
    """Unexpected exceptions return 500 with {detail, code}."""
    db_session_mock.execute.side_effect = RuntimeError("db down")

    resp = client.put(
        f"/user-profile/{current_user_id}",
        json={"skills": ["x"]},
    )

    assert resp.status_code == 500
    detail = resp.json()["detail"]
    assert detail["code"] == "internal_error"

