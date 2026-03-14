from __future__ import annotations

from uuid import UUID

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core.auth import create_access_token, get_current_user_id


@pytest.mark.asyncio
async def test_access_token_round_trip() -> None:
    user_id = UUID("00000000-0000-0000-0000-000000000001")
    token = create_access_token(user_id=user_id)

    resolved_user_id = await get_current_user_id(
        HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    )

    assert resolved_user_id == user_id


@pytest.mark.asyncio
async def test_invalid_access_token_is_rejected() -> None:
    with pytest.raises(HTTPException) as exc:
        await get_current_user_id(
            HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials="not-a-valid-token",
            )
        )

    assert exc.value.status_code == 401
