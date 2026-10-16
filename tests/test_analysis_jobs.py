from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.resume import router as resume_router
from app.core.auth import get_current_user_id
from app.core.database import get_db_session
from app.services.analysis_job_service import create_analysis_job, get_analysis_job
from app.services.resume_service import ResumeService


@pytest.mark.asyncio
async def test_create_and_poll_analysis_job_not_found_for_other_user(
    mocker: pytest.MockFixture,
) -> None:
    """Jobs are owner-scoped."""
    mocker.patch.object(
        ResumeService,
        "analyze_resume",
        mocker.AsyncMock(side_effect=AssertionError("should not run in this test")),
    )
    owner = UUID("00000000-0000-0000-0000-000000000001")
    other = UUID("00000000-0000-0000-0000-000000000002")
    job = await create_analysis_job(
        user_id=owner,
        file_bytes=b"%PDF-1.4\n",
        file_name="cv.pdf",
        content_type="application/pdf",
        target_role="Engineer",
        job_description="Required: Python",
    )
    if job.id:
        from app.services.analysis_job_service import AnalysisJobNotFoundError

        with pytest.raises(AnalysisJobNotFoundError):
            await get_analysis_job(job_id=job.id, user_id=other)


@pytest.fixture()
def resume_app(db_session_mock: AsyncSession, current_user_id: UUID) -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(resume_router)

    async def _override_user() -> UUID:
        return current_user_id

    async def _override_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session_mock

    test_app.dependency_overrides[get_current_user_id] = _override_user
    test_app.dependency_overrides[get_db_session] = _override_db
    return test_app


@pytest.fixture()
def resume_client(resume_app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(resume_app) as client:
        yield client


def test_analyze_jobs_endpoint_returns_202(
    resume_client: TestClient,
    mocker: pytest.MockFixture,
) -> None:
    """Queue endpoint returns immediately with a pending job id."""
    job_id = uuid4()
    from datetime import datetime, timezone

    from app.schemas.analysis_job import AnalysisJobRead

    async def _fake_create(**_kwargs: object) -> AnalysisJobRead:
        now = datetime.now(timezone.utc)
        return AnalysisJobRead(
            id=job_id,
            status="pending",
            created_at=now,
            updated_at=now,
            analysis=None,
            error_code=None,
            error_detail=None,
        )

    mocker.patch("app.api.routes.resume.create_analysis_job", side_effect=_fake_create)
    response = resume_client.post(
        "/resume/analyze-jobs",
        data={
            "target_role": "Engineer",
            "job_description": "Required: Python",
        },
        files={"file": ("cv.pdf", b"%PDF-1.4\n", "application/pdf")},
    )
    assert response.status_code == 202
    assert response.json()["id"] == str(job_id)
    assert response.json()["status"] == "pending"
