from __future__ import annotations

import asyncio
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.startup import initialize_database
from app.main import app


def test_register_login_and_protected_profile_route() -> None:
    asyncio.run(initialize_database())
    email = f"deployment-{uuid4()}@example.com"
    password = "deployment-test-password"

    with TestClient(app) as client:
        register_response = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password},
        )
        assert register_response.status_code == 201
        user_id = register_response.json()["user_id"]

        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]

        unauthorized_response = client.post(
            f"/api/v1/user-profile/{user_id}",
            json={
                "user_id": user_id,
                "skills": ["python", "fastapi"],
                "target_role": "Backend Engineer",
                "experience_level": "mid",
            },
        )
        assert unauthorized_response.status_code == 401

        profile_response = client.post(
            f"/api/v1/user-profile/{user_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "user_id": user_id,
                "skills": ["python", "fastapi"],
                "target_role": "Backend Engineer",
                "experience_level": "mid",
            },
        )
        assert profile_response.status_code == 201
