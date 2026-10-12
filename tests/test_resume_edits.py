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
from app.services.edit_service import (
    EditService,
    ResumeEditNotAcceptableError,
    rescore_resume_text,
)
from app.services.evidence_matcher import match_requirements
from app.services.jd_extraction import extract_requirements
from app.services.resume_service import ResumeAnalysisFailedError
from app.services.scoring import RUBRIC_VERSION

OWNER_ID = UUID("00000000-0000-0000-0000-000000000001")
OTHER_ID = UUID("00000000-0000-0000-0000-000000000002")
ANALYSIS_ID = UUID("00000000-0000-0000-0000-0000000000aa")
EDIT_ID = UUID("00000000-0000-0000-0000-0000000000e1")
VERSION_ID = UUID("00000000-0000-0000-0000-0000000000b1")

SAMPLE_JD = (
    "Required: Python\n"
    "Required: FastAPI\n"
    "Preferred: Kubernetes\n"
)
SAMPLE_RESUME = "Python engineer with FastAPI experience at Acme."
SUPPORTED_REWRITE = "Python and FastAPI engineer at Acme."
VALID_EDITS = {
    "proposals": [
        {
            "original_span": SAMPLE_RESUME,
            "proposed_text": SUPPORTED_REWRITE,
            "requirement_id": None,
            "rationale": "Emphasize FastAPI already on the resume.",
        }
    ]
}


class FakeAdapter:
    def __init__(self, payload: str) -> None:
        self._payload = payload

    async def complete(self, prompt: str) -> str:
        return self._payload


def _auth_headers(user_id: UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id=user_id)}"}


def _matches() -> list[dict]:
    return [
        item.model_dump()
        for item in match_requirements(extract_requirements(SAMPLE_JD), SAMPLE_RESUME)
    ]


def _analysis_row(*, user_id: UUID | None = OWNER_ID) -> SimpleNamespace:
    return SimpleNamespace(
        id=ANALYSIS_ID,
        session_id=uuid4(),
        user_id=user_id,
        file_name="cv.pdf",
        target_role="Backend Engineer",
        resume_text=SAMPLE_RESUME,
        overall_score=66,
        grade="D",
        ats_score=100,
        estimated_level="mid",
        top_strengths=["Python", "FastAPI", "SQLAlchemy"],
        critical_weaknesses=["No metrics", "Missing keywords", "Weak summary"],
        keywords_missing=["Kubernetes"],
        sections=[],
        job_description=SAMPLE_JD,
        job_fit_score=75,
        resume_alignment_score=50,
        application_readiness_score=66,
        rubric_version=RUBRIC_VERSION,
        requirement_matches=_matches(),
        eligibility=[],
        blocked_by_requirement=False,
        completeness_included=False,
        created_at=datetime.now(timezone.utc),
    )


def _edit_row(
    *,
    kind: str,
    status: str = "pending",
    original_span: str | None = SAMPLE_RESUME,
    proposed_text: str = SUPPORTED_REWRITE,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=EDIT_ID,
        analysis_id=ANALYSIS_ID,
        user_id=OWNER_ID,
        kind=kind,
        status=status,
        original_span=original_span,
        proposed_text=proposed_text,
        evidence_span=original_span,
        requirement_id=None,
        rationale="test",
        created_at=datetime.now(timezone.utc),
        reviewed_at=None,
    )


def _queue_execute(db_session_mock: AsyncSession, results: list[object]) -> None:
    queue = list(results)

    async def _execute(_stmt: object) -> object:
        if not queue:
            return SimpleNamespace(
                scalar_one_or_none=lambda: None,
                scalars=lambda: SimpleNamespace(all=lambda: []),
            )
        return queue.pop(0)

    db_session_mock.execute.side_effect = _execute


def _analysis_result(row: object) -> SimpleNamespace:
    return SimpleNamespace(scalar_one_or_none=lambda: row)


def _edit_result(row: object) -> SimpleNamespace:
    return SimpleNamespace(scalar_one_or_none=lambda: row)


def _empty_version_result() -> SimpleNamespace:
    return SimpleNamespace(
        scalar_one_or_none=lambda: None,
        scalars=lambda: SimpleNamespace(all=lambda: []),
    )


async def _refresh(record: object) -> None:
    if getattr(record, "id", None) is None:
        record.id = uuid4()  # type: ignore[attr-defined]
    if getattr(record, "created_at", None) is None:
        record.created_at = datetime.now(timezone.utc)  # type: ignore[attr-defined]


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


@pytest.mark.asyncio
async def test_generate_persists_supported_and_missing_edits(
    db_session_mock: AsyncSession,
    mocker: MockerFixture,
) -> None:
    """Generation stores grounded rewrites and missing-evidence flags, not model scores."""
    analysis = _analysis_row()
    _queue_execute(db_session_mock, [_analysis_result(analysis)])
    db_session_mock.refresh.side_effect = _refresh
    mocker.patch(
        "app.ai.resume_editor.build_local_adapter",
        return_value=FakeAdapter(json.dumps(VALID_EDITS)),
    )

    service = EditService(db_session=db_session_mock)
    result = await service.generate_edits(user_id=OWNER_ID, analysis_id=ANALYSIS_ID)

    kinds = {item.kind for item in result}
    assert "supported_rewrite" in kinds
    assert "missing_qualification" in kinds
    assert all(item.status == "pending" for item in result)
    assert db_session_mock.add.call_count >= 2
    db_session_mock.commit.assert_awaited()
    assert analysis.resume_text == SAMPLE_RESUME
    assert analysis.overall_score == 66


@pytest.mark.asyncio
async def test_malformed_model_output_does_not_persist_edits(
    db_session_mock: AsyncSession,
    mocker: MockerFixture,
) -> None:
    """Invalid edit JSON returns analysis_failed and does not write suggestions."""
    _queue_execute(db_session_mock, [_analysis_result(_analysis_row())])
    mocker.patch(
        "app.ai.resume_editor.build_local_adapter",
        return_value=FakeAdapter("not-json"),
    )
    service = EditService(db_session=db_session_mock)

    with pytest.raises(ResumeAnalysisFailedError) as exc:
        await service.generate_edits(user_id=OWNER_ID, analysis_id=ANALYSIS_ID)

    assert exc.value.code == "analysis_failed"
    db_session_mock.add.assert_not_called()
    db_session_mock.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_reject_pending_suggestion(
    db_session_mock: AsyncSession,
) -> None:
    """Rejecting a pending suggestion records rejected status and does not create a version."""
    edit = _edit_row(kind="unsupported")
    _queue_execute(
        db_session_mock,
        [_analysis_result(_analysis_row()), _edit_result(edit)],
    )
    db_session_mock.refresh.side_effect = _refresh
    service = EditService(db_session=db_session_mock)

    result = await service.reject_edit(
        user_id=OWNER_ID,
        analysis_id=ANALYSIS_ID,
        edit_id=EDIT_ID,
    )

    assert result.status == "rejected"
    assert edit.status == "rejected"
    db_session_mock.add.assert_not_called()
    db_session_mock.commit.assert_awaited()


@pytest.mark.asyncio
async def test_accept_supported_rewrite_creates_rescored_version(
    db_session_mock: AsyncSession,
) -> None:
    """Accepting a grounded rewrite persists a new version and recomputes rubric scores."""
    analysis = _analysis_row()
    edit = _edit_row(kind="supported_rewrite")
    _queue_execute(
        db_session_mock,
        [
            _analysis_result(analysis),
            _analysis_result(analysis),
            _edit_result(edit),
            _empty_version_result(),
        ],
    )
    db_session_mock.refresh.side_effect = _refresh
    service = EditService(db_session=db_session_mock)

    version = await service.accept_edit(
        user_id=OWNER_ID,
        analysis_id=ANALYSIS_ID,
        edit_id=EDIT_ID,
    )

    persisted = db_session_mock.add.call_args[0][0]
    expected = rescore_resume_text(analysis=analysis, resume_text=SUPPORTED_REWRITE)
    assert persisted.resume_text == SUPPORTED_REWRITE
    assert persisted.overall_score == expected.application_readiness_score
    assert persisted.application_readiness_score == expected.application_readiness_score
    assert persisted.rubric_version == RUBRIC_VERSION
    assert persisted.overall_score == persisted.application_readiness_score
    assert analysis.resume_text == SAMPLE_RESUME
    assert analysis.overall_score == 66
    assert edit.status == "accepted"
    assert version.version_number == 1
    assert str(EDIT_ID) in [str(item) for item in version.applied_edit_ids]


@pytest.mark.asyncio
async def test_accept_unsupported_or_missing_is_rejected(
    db_session_mock: AsyncSession,
) -> None:
    """Unsupported and missing-evidence suggestions cannot be applied to a version."""
    analysis = _analysis_row()
    service = EditService(db_session=db_session_mock)

    unsupported = _edit_row(kind="unsupported", proposed_text="Python and Kubernetes at Acme.")
    _queue_execute(
        db_session_mock,
        [_analysis_result(analysis), _analysis_result(analysis), _edit_result(unsupported)],
    )
    with pytest.raises(ResumeEditNotAcceptableError) as unsupported_exc:
        await service.accept_edit(user_id=OWNER_ID, analysis_id=ANALYSIS_ID, edit_id=EDIT_ID)
    assert unsupported_exc.value.code == "edit_not_acceptable"

    missing = _edit_row(
        kind="missing_qualification",
        original_span=None,
        proposed_text="Supply evidence for: Preferred: Kubernetes",
    )
    _queue_execute(
        db_session_mock,
        [_analysis_result(analysis), _analysis_result(analysis), _edit_result(missing)],
    )
    with pytest.raises(ResumeEditNotAcceptableError) as missing_exc:
        await service.accept_edit(user_id=OWNER_ID, analysis_id=ANALYSIS_ID, edit_id=EDIT_ID)
    assert missing_exc.value.code == "edit_not_acceptable"
    db_session_mock.commit.assert_not_awaited()


def test_generate_and_version_routes_require_auth() -> None:
    """Edit and version endpoints return 401 without a Bearer token."""
    with TestClient(app) as client:
        generate = client.post(f"/api/v1/resume/analyses/{ANALYSIS_ID}/edits")
        listing = client.get(f"/api/v1/resume/analyses/{ANALYSIS_ID}/edits")
        versions = client.get(f"/api/v1/resume/analyses/{ANALYSIS_ID}/versions")

    assert generate.status_code == 401
    assert listing.status_code == 401
    assert versions.status_code == 401
    assert generate.json()["detail"]["code"] == "unauthorized"


def test_cross_user_edit_access_returns_same_404_as_missing(
    resume_client: TestClient,
    db_session_mock: AsyncSession,
) -> None:
    """Another user's analysis/edit/version is indistinguishable from a missing id."""
    db_session_mock.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda: None)

    generate = resume_client.post(f"/resume/analyses/{ANALYSIS_ID}/edits")
    other_edit = resume_client.post(
        f"/resume/analyses/{ANALYSIS_ID}/edits/{EDIT_ID}/accept"
    )
    missing_version = resume_client.get(
        f"/resume/analyses/{ANALYSIS_ID}/versions/00000000-0000-0000-0000-0000000000ff"
    )

    assert generate.status_code == 404
    assert other_edit.status_code == 404
    assert missing_version.status_code == 404
    assert generate.json()["detail"]["code"] == "not_found"
    assert generate.json() == other_edit.json()


def test_owner_can_list_edits_and_versions(
    resume_client: TestClient,
    db_session_mock: AsyncSession,
    current_user_id: UUID,
) -> None:
    """The owner can list their suggestions and versions; resume_text stays off the list."""
    analysis = _analysis_row(user_id=current_user_id)
    edit = _edit_row(kind="supported_rewrite")
    version = SimpleNamespace(
        id=VERSION_ID,
        analysis_id=ANALYSIS_ID,
        version_number=1,
        overall_score=66,
        grade="D",
        created_at=datetime.now(timezone.utc),
    )
    _queue_execute(
        db_session_mock,
        [
            _analysis_result(analysis),
            SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [edit])),
            _analysis_result(analysis),
            SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [version])),
        ],
    )

    edits = resume_client.get(f"/resume/analyses/{ANALYSIS_ID}/edits")
    versions = resume_client.get(f"/resume/analyses/{ANALYSIS_ID}/versions")

    assert edits.status_code == 200
    assert versions.status_code == 200
    assert edits.json()[0]["id"] == str(EDIT_ID)
    assert "resume_text" not in edits.json()[0]
    assert versions.json()[0]["id"] == str(VERSION_ID)
    assert "resume_text" not in versions.json()[0]


def test_score_recompute_matches_rubric_not_model_numbers() -> None:
    """Re-evaluation uses stored JD requirements and rubric v1.0.0, never model scores."""
    analysis = _analysis_row()
    scored = rescore_resume_text(analysis=analysis, resume_text=SUPPORTED_REWRITE)
    assert scored.rubric_version == RUBRIC_VERSION
    assert scored.application_readiness_score == scored.application_readiness_score
    assert scored.application_readiness_score != 99
