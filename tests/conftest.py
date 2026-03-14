from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from typing import Any
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.user_profile import router as user_profile_router
from app.core.auth import get_current_user_id
from app.core.database import get_db_session


@pytest.fixture()
def current_user_id() -> UUID:
    return UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture()
def other_user_id() -> UUID:
    return UUID("00000000-0000-0000-0000-000000000002")


@pytest.fixture()
def db_session_mock(mocker: MockerFixture) -> AsyncSession:
    session = mocker.create_autospec(AsyncSession, instance=True)
    session.execute = mocker.AsyncMock()
    session.commit = mocker.AsyncMock()
    session.refresh = mocker.AsyncMock()
    session.rollback = mocker.AsyncMock()
    session.add = mocker.Mock()
    return session


@pytest.fixture()
def fastapi_app(
    current_user_id: UUID,
    db_session_mock: AsyncSession,
) -> FastAPI:
    app = FastAPI()
    app.include_router(user_profile_router)

    async def _override_get_current_user_id() -> UUID:
        return current_user_id

    async def _override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session_mock

    app.dependency_overrides[get_current_user_id] = _override_get_current_user_id
    app.dependency_overrides[get_db_session] = _override_get_db_session
    return app


@pytest.fixture()
def client(fastapi_app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(fastapi_app) as c:
        yield c

