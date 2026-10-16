from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.resume import router as resume_router
from app.core.auth import get_current_user_id
from app.core.database import get_db_session
from app.main import app
from app.services.resume_service import (
    ResumeSchemaOutdatedError,
    ResumeService,
    build_analytics,
)

OWNER_ID = UUID("00000000-0000-0000-0000-000000000001")
OTHER_ID = UUID("00000000-0000-0000-0000-000000000002")
ANALYSIS_A = UUID("00000000-0000-0000-0000-0000000000aa")
ANALYSIS_B = UUID("00000000-0000-0000-0000-0000000000bb")

CREATED_NEW = datetime(2026, 10, 12, 15, 0, tzinfo=timezone.utc)
CREATED_OLD = CREATED_NEW - timedelta(days=2)


def _match(
    *,
    evidence_state: str,
    importance: str = "preferred",
    text: str = "Python",
) -> dict[str, object]:
    return {
        "id": f"req-{text}-{evidence_state}",
        "text": text,
        "category": "skill",
        "importance": importance,
        "is_eligibility": False,
        "evidence_state": evidence_state,
        "evidence_span": None,
        "rationale": "fixture",
    }


def _row(
    *,
    analysis_id: UUID,
    created_at: datetime,
    target_role: str = "Backend Engineer",
    overall_score: int = 72,
    job_fit_score: int | None = 70,
    resume_alignment_score: int | None = 68,
    application_readiness_score: int | None = 72,
    rubric_version: str | None = "v1.0.0",
    blocked_by_requirement: bool = False,
    requirement_matches: list[dict[str, object]] | None = None,
    keywords_missing: list[str] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=analysis_id,
        session_id=uuid4(),
        user_id=OWNER_ID,
        file_name="cv.pdf",
        target_role=target_role,
        resume_text="SECRET RESUME TEXT",
        overall_score=overall_score,
        grade="B",
        ats_score=65,
        estimated_level="mid",
        top_strengths=["Python"],
        critical_weaknesses=["No metrics"],
        keywords_missing=keywords_missing or ["Kubernetes"],
        sections=[],
        job_description="Required: Python",
        job_fit_score=job_fit_score,
        resume_alignment_score=resume_alignment_score,
        application_readiness_score=application_readiness_score,
        rubric_version=rubric_version,
        requirement_matches=requirement_matches
        or [
            _match(evidence_state="confirmed", importance="mandatory", text="Python"),
            _match(evidence_state="not_found", importance="preferred", text="Kubernetes"),
        ],
        eligibility=[],
        blocked_by_requirement=blocked_by_requirement,
        completeness_included=True,
        created_at=created_at,
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


def test_analytics_without_token_returns_401() -> None:
    """Analytics requires a Bearer token."""
    with TestClient(app) as client:
        response = client.get("/api/v1/resume/analytics")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_analytics_query_filters_by_owner(
    db_session_mock: AsyncSession,
    current_user_id: UUID,
) -> None:
    """Analytics SQL is scoped to the caller, so other users and NULL owners are excluded."""
    empty_analyses = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))
    no_profile = SimpleNamespace(scalar_one_or_none=lambda: None)
    db_session_mock.execute.side_effect = [empty_analyses, no_profile]
    service = ResumeService(db_session=db_session_mock)
    await service.get_analytics_for_user(user_id=current_user_id)

    sql_calls = [
        str(call.args[0].compile(compile_kwargs={"literal_binds": True})).lower()
        for call in db_session_mock.execute.await_args_list
    ]
    analysis_sql = next(sql for sql in sql_calls if "resume_analyses.user_id" in sql)
    assert current_user_id.hex in analysis_sql
    assert OTHER_ID.hex not in analysis_sql
    assert "is null" not in analysis_sql
    assert "limit" in analysis_sql


def test_analytics_empty_history_is_honest(
    resume_client: TestClient,
    db_session_mock: AsyncSession,
) -> None:
    """An owner with no analyses gets zeros, not fabricated scores or resume text."""
    empty_analyses = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))
    no_profile = SimpleNamespace(scalar_one_or_none=lambda: None)
    db_session_mock.execute.side_effect = [empty_analyses, no_profile]

    response = resume_client.get("/resume/analytics")

    assert response.status_code == 200
    body = response.json()
    assert body["analysis_count"] == 0
    assert body["requirement_count"] == 0
    assert body["blocked_count"] == 0
    assert body["mandatory_gap_count"] == 0
    assert body["latest_created_at"] is None
    assert body["rubric_versions"] == []
    assert body["scores"] == []
    assert body["roles"] == []
    assert body["missing_terminology"] == []
    assert body["edits"]["total_edits"] == 0
    assert body["edit_kinds"] == []
    assert body["version_deltas"] == []
    assert body["eligibility_rollups"] == []
    assert body["profile_skill_coverage"] == []
    assert body["requirement_heatmap"] == []
    assert body["importance_evidence"] == []
    assert body["role_coverage_matrix"] == []
    assert {item["state"]: item["count"] for item in body["evidence"]} == {
        "confirmed": 0,
        "partial": 0,
        "not_found": 0,
        "contradicted": 0,
        "unknown": 0,
    }
    assert "resume_text" not in body
    assert "SECRET" not in response.text


def test_analytics_aggregates_owned_rows_and_omits_resume_text(
    resume_client: TestClient,
    db_session_mock: AsyncSession,
) -> None:
    """Evidence, gaps, terms, and oldest-first scores come from owned rows only."""
    newer = _row(
        analysis_id=ANALYSIS_A,
        created_at=CREATED_NEW,
        blocked_by_requirement=True,
        requirement_matches=[
            _match(evidence_state="confirmed", importance="mandatory", text="Python"),
            _match(evidence_state="not_found", importance="mandatory", text="On-call"),
            _match(evidence_state="contradicted", importance="preferred", text="Staff"),
        ],
        keywords_missing=["Kubernetes", "Terraform"],
    )
    older = _row(
        analysis_id=ANALYSIS_B,
        created_at=CREATED_OLD,
        target_role="Data Engineer",
        overall_score=40,
        job_fit_score=None,
        resume_alignment_score=None,
        application_readiness_score=None,
        rubric_version=None,
        requirement_matches=[
            _match(evidence_state="partial", importance="preferred", text="SQL"),
        ],
        keywords_missing=["Kubernetes"],
    )
    analysis_result = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [newer, older]))
    empty_result = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))
    profile_result = SimpleNamespace(scalar_one_or_none=lambda: None)
    db_session_mock.execute.side_effect = [
        analysis_result,
        empty_result,
        empty_result,
        profile_result,
    ]

    response = resume_client.get("/resume/analytics")

    assert response.status_code == 200
    body = response.json()
    assert body["analysis_count"] == 2
    assert body["requirement_count"] == 4
    assert body["blocked_count"] == 1
    assert body["mandatory_gap_count"] == 1
    assert body["latest_created_at"].startswith("2026-10-12T15:00:00")
    assert body["rubric_versions"] == ["v1.0.0"]
    counts = {item["state"]: item["count"] for item in body["evidence"]}
    assert counts == {
        "confirmed": 1,
        "partial": 1,
        "not_found": 1,
        "contradicted": 1,
        "unknown": 0,
    }
    assert [point["id"] for point in body["scores"]] == [str(ANALYSIS_B), str(ANALYSIS_A)]
    assert body["scores"][0]["application_readiness_score"] is None
    assert body["scores"][1]["application_readiness_score"] == 72
    assert "resume_text" not in body
    assert "SECRET RESUME TEXT" not in response.text
    roles = {item["target_role"]: item for item in body["roles"]}
    assert roles["Backend Engineer"]["avg_readiness"] == 72.0
    assert roles["Data Engineer"]["avg_readiness"] is None
    assert roles["Data Engineer"]["confirmed"] == 0
    terms = {item["term"]: item["count"] for item in body["missing_terminology"]}
    assert terms["Kubernetes"] == 2
    assert terms["Terraform"] == 1


def test_build_analytics_skips_null_readiness_instead_of_zeroing() -> None:
    """Null application-readiness stays null so charts can gap the point."""
    row = _row(
        analysis_id=ANALYSIS_A,
        created_at=CREATED_NEW,
        application_readiness_score=None,
        job_fit_score=None,
        resume_alignment_score=None,
    )
    payload = build_analytics([row])
    assert payload.scores[0].application_readiness_score is None
    assert payload.roles[0].avg_readiness is None


def test_build_analytics_groups_importance_and_role_matrix() -> None:
    """Mandatory vs preferred counts and role matrix rows come from requirement_matches."""
    row = _row(
        analysis_id=ANALYSIS_A,
        created_at=CREATED_NEW,
        requirement_matches=[
            _match(evidence_state="confirmed", importance="mandatory", text="Python"),
            _match(evidence_state="not_found", importance="preferred", text="Kubernetes"),
        ],
    )
    payload = build_analytics([row])
    assert any(
        bucket.importance == "mandatory" and bucket.state == "confirmed"
        for bucket in payload.importance_evidence
    )
    assert len(payload.role_coverage_matrix) == 2
    assert payload.role_coverage_matrix[0].requirement_text in {"Python", "Kubernetes"}


def test_build_analytics_computes_supported_rewrite_accept_rate() -> None:
    """Accept rate uses accepted ÷ (accepted + rejected) for supported_rewrite only."""
    row = _row(analysis_id=ANALYSIS_A, created_at=CREATED_NEW)
    edits = [
        SimpleNamespace(kind="supported_rewrite", status="accepted"),
        SimpleNamespace(kind="supported_rewrite", status="rejected"),
        SimpleNamespace(kind="unsupported", status="pending"),
    ]
    payload = build_analytics([row], edits=edits)
    assert payload.edits.supported_rewrite_generated == 2
    assert payload.edits.supported_rewrite_accept_rate == 0.5
    assert payload.edits.pending == 1


def test_build_analytics_builds_version_delta_and_heatmap() -> None:
    """Version lift and requirement heatmap come from stored matches, not resume text."""
    row = _row(
        analysis_id=ANALYSIS_A,
        created_at=CREATED_NEW,
        application_readiness_score=60,
    )
    versions = [
        SimpleNamespace(
            analysis_id=ANALYSIS_A,
            version_number=1,
            application_readiness_score=72,
            overall_score=72,
            rubric_version="v1.0.0",
        )
    ]
    payload = build_analytics([row], versions=versions)
    assert len(payload.version_deltas) == 1
    assert payload.version_deltas[0].delta == 12
    assert len(payload.requirement_heatmap) >= 1
    assert "resume_text" not in payload.model_dump()


def test_analytics_target_role_query_filters_in_memory(
    resume_client: TestClient,
    db_session_mock: AsyncSession,
) -> None:
    """Optional target_role keeps only matching analyses in the aggregate window."""
    newer = _row(analysis_id=ANALYSIS_A, created_at=CREATED_NEW)
    older = _row(
        analysis_id=ANALYSIS_B,
        created_at=CREATED_OLD,
        target_role="Data Engineer",
    )
    analysis_result = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [newer, older]))
    empty_result = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))
    profile_result = SimpleNamespace(scalar_one_or_none=lambda: None)
    db_session_mock.execute.side_effect = [
        analysis_result,
        empty_result,
        empty_result,
        profile_result,
    ]

    response = resume_client.get("/resume/analytics?target_role=Data%20Engineer")

    assert response.status_code == 200
    body = response.json()
    assert body["analysis_count"] == 1
    assert body["roles"][0]["target_role"] == "Data Engineer"


def test_build_analytics_never_copies_resume_text() -> None:
    """The aggregate model has no resume_text field even when rows contain it."""
    payload = build_analytics([_row(analysis_id=ANALYSIS_A, created_at=CREATED_NEW)])
    dumped = payload.model_dump()
    assert "resume_text" not in dumped
    assert "SECRET RESUME TEXT" not in str(dumped)


def test_build_analytics_eligibility_and_profile_skill_coverage() -> None:
    """Eligibility rollups and profile skill mentions come from stored analysis rows."""
    row = _row(
        analysis_id=ANALYSIS_A,
        created_at=CREATED_NEW,
        requirement_matches=[
            _match(evidence_state="confirmed", importance="mandatory", text="Python 3"),
        ],
    )
    row.eligibility = [
        {
            "text": "Must be authorized to work in the US",
            "status": "confirmed_not_met",
            "rationale": "fixture",
        }
    ]
    payload = build_analytics([row], profile_skills=["Python", "Rust"])
    assert len(payload.eligibility_rollups) == 1
    assert payload.eligibility_rollups[0].confirmed_not_met == 1
    python_row = next(item for item in payload.profile_skill_coverage if item.skill == "Python")
    assert python_row.requirement_mentions == 1
    assert python_row.confirmed == 1
    rust_row = next(item for item in payload.profile_skill_coverage if item.skill == "Rust")
    assert rust_row.requirement_mentions == 0


@pytest.mark.asyncio
async def test_analytics_maps_missing_column_to_schema_outdated(
    db_session_mock: AsyncSession,
    current_user_id: UUID,
) -> None:
    """Stale sqlite without user_id is schema_outdated, not an unhandled 500."""
    db_session_mock.execute.side_effect = OperationalError(
        "SELECT",
        {},
        Exception("no such column: resume_analyses.user_id"),
    )
    service = ResumeService(db_session=db_session_mock)
    with pytest.raises(ResumeSchemaOutdatedError) as exc:
        await service.get_analytics_for_user(user_id=current_user_id)
    assert exc.value.code == "schema_outdated"
    assert exc.value.http_status == 503


def test_analytics_route_returns_503_schema_outdated(
    resume_client: TestClient,
    db_session_mock: AsyncSession,
) -> None:
    """Analytics surfaces schema_outdated instead of Internal server error."""
    db_session_mock.execute.side_effect = OperationalError(
        "SELECT",
        {},
        Exception("no such column: resume_analyses.user_id"),
    )
    response = resume_client.get("/resume/analytics")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "schema_outdated"
