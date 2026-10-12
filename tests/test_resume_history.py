from __future__ import annotations

import json
from collections.abc import AsyncGenerator, Generator
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.resume import router as resume_router
from app.core.auth import create_access_token, get_current_user_id
from app.core.database import get_db_session
from app.main import app
from app.services.resume_service import ResumeAnalysisNotFoundError, ResumeService

OWNER_ID = UUID("00000000-0000-0000-0000-000000000001")
OTHER_ID = UUID("00000000-0000-0000-0000-000000000002")
ANALYSIS_ID = UUID("00000000-0000-0000-0000-0000000000aa")

SAMPLE_JD = (
    "Required: Python\n"
    "Required: FastAPI\n"
    "Preferred: Kubernetes\n"
)
VALID_EXTRACTION = {"requirements": [], "estimated_level": "mid"}
VALID_ANALYSIS = {
    "overall_score": 72,
    "grade": "B",
    "ats_score": 65,
    "estimated_level": "mid",
    "top_strengths": ["Python", "FastAPI", "SQLAlchemy"],
    "critical_weaknesses": ["No metrics", "Missing keywords", "Weak summary"],
    "keywords_missing": ["Kubernetes"],
    "sections": [
        {
            "name": "Work Experience",
            "score": 70,
            "status": "needs_improvement",
            "feedback": "Add measurable outcomes.",
            "suggestions": ["Quantify impact"],
        }
    ],
}


class FakeAdapter:
    async def complete(self, prompt: str) -> str:
        return json.dumps(VALID_EXTRACTION)


def _auth_headers(user_id: UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id=user_id)}"}


def _analysis_row(*, user_id: UUID | None, analysis_id: UUID = ANALYSIS_ID) -> SimpleNamespace:
    return SimpleNamespace(
        id=analysis_id,
        session_id=uuid4(),
        user_id=user_id,
        file_name="cv.pdf",
        target_role="Backend Engineer",
        resume_text="SECRET RESUME TEXT",
        overall_score=72,
        grade="B",
        ats_score=65,
        estimated_level="mid",
        top_strengths=VALID_ANALYSIS["top_strengths"],
        critical_weaknesses=VALID_ANALYSIS["critical_weaknesses"],
        keywords_missing=VALID_ANALYSIS["keywords_missing"],
        sections=VALID_ANALYSIS["sections"],
        job_description=None,
        job_fit_score=None,
        resume_alignment_score=None,
        application_readiness_score=None,
        rubric_version=None,
        requirement_matches=[],
        eligibility=[],
        blocked_by_requirement=False,
        completeness_included=False,
        created_at=datetime.now(timezone.utc),
    )


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


def test_analyze_with_real_jwt_persists_token_subject(
    mocker: MockerFixture,
    db_session_mock: AsyncSession,
) -> None:
    """A real Bearer token's sub is stored as user_id on the analysis row."""
    mocker.patch(
        "app.services.resume_service._extract_text_from_pdf",
        return_value="Python engineer with FastAPI experience at Acme.",
    )
    mocker.patch(
        "app.ai.resume_analyzer.build_local_adapter",
        return_value=FakeAdapter(),
    )

    async def _override_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session_mock

    async def _refresh(record: object) -> None:
        record.id = ANALYSIS_ID  # type: ignore[attr-defined]
        record.session_id = uuid4()  # type: ignore[attr-defined]
        record.created_at = datetime.now(timezone.utc)  # type: ignore[attr-defined]

    db_session_mock.refresh.side_effect = _refresh
    app.dependency_overrides[get_db_session] = _override_db
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/resume/analyze",
                files={"file": ("cv.pdf", b"%PDF-fake", "application/pdf")},
                data={
                "target_role": "Backend Engineer",
                "job_description": SAMPLE_JD,
                "user_id": str(OTHER_ID),
            },
                headers=_auth_headers(OWNER_ID),
            )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert response.status_code == 200
    persisted = db_session_mock.add.call_args[0][0]
    assert persisted.user_id == OWNER_ID
    assert persisted.user_id != OTHER_ID


def test_analyze_without_token_returns_401() -> None:
    """Unauthenticated analyze returns 401 and does not reach persistence."""
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/resume/analyze",
            files={"file": ("cv.pdf", b"%PDF-fake", "application/pdf")},
            data={"target_role": "Backend Engineer", "job_description": SAMPLE_JD},
        )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "unauthorized"


def test_list_and_read_without_token_return_401() -> None:
    """History endpoints require a Bearer token."""
    with TestClient(app) as client:
        list_response = client.get("/api/v1/resume/analyses")
        read_response = client.get(f"/api/v1/resume/analyses/{ANALYSIS_ID}")

    assert list_response.status_code == 401
    assert read_response.status_code == 401
    assert list_response.json()["detail"]["code"] == "unauthorized"
    assert read_response.json()["detail"]["code"] == "unauthorized"


def test_analyze_persists_token_subject_not_client_user_id(
    resume_client: TestClient,
    db_session_mock: AsyncSession,
    current_user_id: UUID,
    other_user_id: UUID,
    mocker: MockerFixture,
) -> None:
    """New analyses are owned by the JWT subject even if the client sends another user_id."""
    mocker.patch(
        "app.services.resume_service._extract_text_from_pdf",
        return_value="Python engineer with FastAPI experience at Acme.",
    )
    mocker.patch(
        "app.ai.resume_analyzer.build_local_adapter",
        return_value=FakeAdapter(),
    )

    async def _refresh(record: object) -> None:
        record.id = ANALYSIS_ID  # type: ignore[attr-defined]
        record.session_id = uuid4()  # type: ignore[attr-defined]
        record.created_at = datetime.now(timezone.utc)  # type: ignore[attr-defined]

    db_session_mock.refresh.side_effect = _refresh

    response = resume_client.post(
        "/resume/analyze",
        files={"file": ("cv.pdf", b"%PDF-fake", "application/pdf")},
        data={
            "target_role": "Backend Engineer",
            "job_description": SAMPLE_JD,
            "user_id": str(other_user_id),
        },
    )

    assert response.status_code == 200
    persisted = db_session_mock.add.call_args[0][0]
    assert persisted.user_id == current_user_id
    assert persisted.user_id != other_user_id
    body = response.json()
    assert "resume_text" not in body
    assert set(body.keys()) == {
        "id",
        "session_id",
        "file_name",
        "target_role",
        "overall_score",
        "grade",
        "ats_score",
        "estimated_level",
        "top_strengths",
        "critical_weaknesses",
        "keywords_missing",
        "sections",
        "created_at",
        "job_description",
        "job_fit_score",
        "resume_alignment_score",
        "application_readiness_score",
        "rubric_version",
        "requirement_matches",
        "eligibility",
        "blocked_by_requirement",
        "completeness_included",
    }


@pytest.mark.asyncio
async def test_list_query_filters_by_owner_and_excludes_legacy_nulls(
    db_session_mock: AsyncSession,
    current_user_id: UUID,
) -> None:
    """List SQL is scoped to the caller, so NULL legacy owners are not returned."""
    db_session_mock.execute.return_value = SimpleNamespace(
        scalars=lambda: SimpleNamespace(all=lambda: [])
    )
    service = ResumeService(db_session=db_session_mock)
    await service.list_analyses_for_user(user_id=current_user_id)

    stmt = db_session_mock.execute.await_args.args[0]
    sql = str(stmt.compile(compile_kwargs={"literal_binds": True})).lower()
    assert "resume_analyses.user_id" in sql
    assert current_user_id.hex in sql
    assert "is null" not in sql


@pytest.mark.asyncio
async def test_get_query_requires_matching_owner(
    db_session_mock: AsyncSession,
    current_user_id: UUID,
) -> None:
    """Read SQL requires both analysis id and caller user_id."""
    db_session_mock.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda: None)
    service = ResumeService(db_session=db_session_mock)

    with pytest.raises(ResumeAnalysisNotFoundError) as exc:
        await service.get_analysis_for_user(
            user_id=current_user_id,
            analysis_id=ANALYSIS_ID,
        )

    assert exc.value.http_status == 404
    assert exc.value.code == "not_found"
    stmt = db_session_mock.execute.await_args.args[0]
    sql = str(stmt.compile(compile_kwargs={"literal_binds": True})).lower()
    assert "resume_analyses.user_id" in sql
    assert "resume_analyses.id" in sql
    assert current_user_id.hex in sql
    assert ANALYSIS_ID.hex in sql


def test_owner_can_list_and_read_own_analysis(
    resume_client: TestClient,
    db_session_mock: AsyncSession,
    current_user_id: UUID,
) -> None:
    """The owner can list and read their analysis; resume_text is never returned."""
    row = _analysis_row(user_id=current_user_id)
    db_session_mock.execute.return_value = SimpleNamespace(
        scalars=lambda: SimpleNamespace(all=lambda: [row]),
        scalar_one_or_none=lambda: row,
    )

    list_response = resume_client.get("/resume/analyses")
    assert list_response.status_code == 200
    items = list_response.json()
    assert len(items) == 1
    assert items[0]["id"] == str(ANALYSIS_ID)
    assert "resume_text" not in items[0]
    assert "SECRET RESUME TEXT" not in list_response.text

    read_response = resume_client.get(f"/resume/analyses/{ANALYSIS_ID}")
    assert read_response.status_code == 200
    body = read_response.json()
    assert body["id"] == str(ANALYSIS_ID)
    assert "resume_text" not in body
    assert "SECRET RESUME TEXT" not in read_response.text


def test_other_user_read_returns_same_404_as_missing(
    resume_client: TestClient,
    db_session_mock: AsyncSession,
) -> None:
    """Cross-user reads return the same 404 shape as an unknown id."""
    db_session_mock.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda: None)

    other_response = resume_client.get(f"/resume/analyses/{ANALYSIS_ID}")
    missing_response = resume_client.get(
        "/resume/analyses/00000000-0000-0000-0000-0000000000ff"
    )

    assert other_response.status_code == 404
    assert missing_response.status_code == 404
    assert other_response.json() == missing_response.json()
    assert other_response.json()["detail"]["code"] == "not_found"


def test_list_does_not_include_other_users_rows(
    resume_client: TestClient,
    db_session_mock: AsyncSession,
) -> None:
    """List endpoint only serializes the query result, which is owner-filtered."""
    db_session_mock.execute.return_value = SimpleNamespace(
        scalars=lambda: SimpleNamespace(all=lambda: [])
    )

    response = resume_client.get("/resume/analyses")

    assert response.status_code == 200
    assert response.json() == []
    stmt = db_session_mock.execute.await_args.args[0]
    sql = str(stmt.compile(compile_kwargs={"literal_binds": True})).lower()
    assert "resume_analyses.user_id" in sql
    assert OWNER_ID.hex in sql
    assert OTHER_ID.hex not in sql
