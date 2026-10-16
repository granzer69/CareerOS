from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.local_inference import (
    LocalModelNotFoundError,
    LlamaCppAdapter,
    build_local_adapter,
    require_local_model_file,
)
from app.services.resume_service import (
    ResumeAnalysisFailedError,
    ResumeJobDescriptionError,
    ResumeService,
)
from app.core.auth import create_access_token
from app.core.config import settings
from app.main import app
from app.schemas.resume_analysis import ResumeAnalysisRead
from app.services.evidence_matcher import match_requirements
from app.services.jd_extraction import extract_requirements
from app.services.scoring import RUBRIC_VERSION, score_application

SAMPLE_JD = (
    "Required: Python\n"
    "Required: FastAPI\n"
    "Preferred: Kubernetes\n"
)
SAMPLE_RESUME = "Python engineer with FastAPI experience at Acme."
VALID_EXTRACTION: dict[str, Any] = {"requirements": [], "estimated_level": "mid"}
VALID_UNDERSTANDING: dict[str, Any] = {
    "role_summary": "Backend engineer role focused on Python API delivery.",
    "objectives": ["Build and maintain Python services"],
    "success_criteria": [],
    "estimated_level": "mid",
}
INVENTED_SCORES: dict[str, Any] = {
    "overall_score": 72,
    "grade": "B",
    "ats_score": 65,
    "estimated_level": "mid",
    "top_strengths": ["Python", "FastAPI", "SQLAlchemy"],
    "critical_weaknesses": ["No metrics", "Missing keywords", "Weak summary"],
    "keywords_missing": ["Kubernetes"],
    "sections": [],
}

RESUME_READ_FIELDS = {
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
    "jd_insights",
}


class FakeAdapter:
    def __init__(self, payload: str) -> None:
        self._payload = payload

    async def complete(self, prompt: str, *, max_tokens: int | None = None) -> str:
        if "requirement_index" in prompt:
            return json.dumps({"matches": []})
        if '"requirements"' in prompt and "evidence_state" not in prompt:
            return self._payload
        if "success_criteria" in prompt and "role_summary" in prompt:
            return json.dumps(VALID_UNDERSTANDING)
        return self._payload


class RaisingAdapter:
    def __init__(self, exc: BaseException) -> None:
        self._exc = exc

    async def complete(self, prompt: str, *, max_tokens: int | None = None) -> str:
        raise self._exc


def _auth_headers(user_id: UUID | None = None) -> dict[str, str]:
    token = create_access_token(
        user_id=user_id or UUID("00000000-0000-0000-0000-000000000001")
    )
    return {"Authorization": f"Bearer {token}"}


def _analyze_form() -> dict[str, str]:
    return {"target_role": "Backend Engineer", "job_description": SAMPLE_JD}


def _patch_extraction(mocker: MockerFixture) -> None:
    mocker.patch(
        "app.services.resume_service._extract_text_from_pdf",
        return_value=SAMPLE_RESUME,
    )


async def _assign_persisted_fields(record: object) -> None:
    record.id = uuid4()  # type: ignore[attr-defined]
    record.session_id = uuid4()  # type: ignore[attr-defined]
    record.created_at = datetime.now(timezone.utc)  # type: ignore[attr-defined]


def _expected_scores() -> Any:
    matches = match_requirements(extract_requirements(SAMPLE_JD), SAMPLE_RESUME)
    return score_application(
        matches=matches,
        resume_text=SAMPLE_RESUME,
        estimated_level_hint="mid",
    )


@pytest.mark.asyncio
async def test_mocked_adapter_returns_resume_analysis_read_shape(
    db_session_mock: AsyncSession,
    mocker: MockerFixture,
) -> None:
    """A mocked local completion persists rubric scores and the ResumeAnalysisRead contract."""
    _patch_extraction(mocker)
    mocker.patch(
        "app.ai.local_inference.build_local_adapter",
        return_value=FakeAdapter(json.dumps(VALID_EXTRACTION)),
    )
    db_session_mock.refresh.side_effect = _assign_persisted_fields
    expected = _expected_scores()

    owner_id = UUID("00000000-0000-0000-0000-000000000001")
    service = ResumeService(db_session=db_session_mock)
    result = await service.analyze_resume(
        file_bytes=b"%PDF-fake",
        file_name="cv.pdf",
        content_type="application/pdf",
        target_role="Backend Engineer",
        job_description=SAMPLE_JD,
        user_id=owner_id,
    )

    assert isinstance(result, ResumeAnalysisRead)
    assert set(result.model_dump().keys()) == RESUME_READ_FIELDS
    assert result.overall_score == expected.application_readiness_score
    assert result.overall_score != INVENTED_SCORES["overall_score"]
    assert result.job_fit_score == expected.job_fit_score
    assert result.resume_alignment_score == expected.resume_alignment_score
    assert result.application_readiness_score == expected.application_readiness_score
    assert result.grade == expected.grade
    assert result.rubric_version == RUBRIC_VERSION
    persisted = db_session_mock.add.call_args[0][0]
    assert persisted.user_id == owner_id
    assert persisted.overall_score == persisted.application_readiness_score
    db_session_mock.commit.assert_awaited()


def test_missing_weights_return_model_unavailable(mocker: MockerFixture) -> None:
    """A missing GGUF file returns 503 model_unavailable without leaking the path or importing llama_cpp."""
    missing_path = "/tmp/careeros-missing-model.gguf"
    mocker.patch.object(settings, "LOCAL_MODEL_PATH", missing_path)
    _patch_extraction(mocker)

    with pytest.raises(LocalModelNotFoundError):
        build_local_adapter()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/resume/analyze",
            files={"file": ("cv.pdf", b"%PDF-fake", "application/pdf")},
            data=_analyze_form(),
            headers=_auth_headers(),
        )

    assert response.status_code == 503
    body = response.json()
    assert body["detail"]["code"] == "model_unavailable"
    assert body["detail"]["detail"] == "Local model weights are not available"
    assert missing_path not in response.text
    assert "llama_cpp" not in sys.modules


def test_adapter_exception_is_mapped_without_leaking_details(
    mocker: MockerFixture,
) -> None:
    """Unexpected adapter errors map to 503 inference_failed without leaking internals."""
    _patch_extraction(mocker)
    mocker.patch(
        "app.ai.local_inference.build_local_adapter",
        return_value=RaisingAdapter(RuntimeError("prompt-secret")),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/resume/analyze",
            files={"file": ("cv.pdf", b"%PDF-fake", "application/pdf")},
            data=_analyze_form(),
            headers=_auth_headers(),
        )

    assert response.status_code == 503
    body = response.json()
    assert body["detail"]["code"] == "inference_failed"
    assert body["detail"]["detail"] == "Local inference failed"
    assert "prompt-secret" not in response.text


@pytest.mark.asyncio
async def test_invalid_json_falls_back_to_deterministic_jd(
    db_session_mock: AsyncSession,
    mocker: MockerFixture,
) -> None:
    """Malformed model JSON still scores deterministic JD requirements."""
    _patch_extraction(mocker)
    mocker.patch(
        "app.ai.local_inference.build_local_adapter",
        return_value=FakeAdapter("not-json"),
    )
    db_session_mock.refresh.side_effect = _assign_persisted_fields

    service = ResumeService(db_session=db_session_mock)
    await service.analyze_resume(
        file_bytes=b"%PDF-fake",
        file_name="cv.pdf",
        content_type="application/pdf",
        target_role="Backend Engineer",
        job_description=SAMPLE_JD,
        user_id=UUID("00000000-0000-0000-0000-000000000001"),
    )

    db_session_mock.add.assert_called_once()
    db_session_mock.commit.assert_awaited()


@pytest.mark.asyncio
async def test_model_numeric_scores_are_rejected_but_deterministic_jd_still_scores(
    db_session_mock: AsyncSession,
    mocker: MockerFixture,
) -> None:
    """Invented score JSON from the model is ignored; rubric uses deterministic JD rows."""
    _patch_extraction(mocker)
    mocker.patch(
        "app.ai.local_inference.build_local_adapter",
        return_value=FakeAdapter(json.dumps(INVENTED_SCORES)),
    )
    db_session_mock.refresh.side_effect = _assign_persisted_fields

    service = ResumeService(db_session=db_session_mock)
    result = await service.analyze_resume(
        file_bytes=b"%PDF-fake",
        file_name="cv.pdf",
        content_type="application/pdf",
        target_role="Backend Engineer",
        job_description=SAMPLE_JD,
        user_id=UUID("00000000-0000-0000-0000-000000000001"),
    )

    assert result.overall_score != INVENTED_SCORES["overall_score"]
    db_session_mock.add.assert_called_once()
    db_session_mock.commit.assert_awaited()


@pytest.mark.asyncio
async def test_whitespace_job_description_is_rejected(
    db_session_mock: AsyncSession,
    mocker: MockerFixture,
) -> None:
    """Whitespace-only JDs never reach inference or persistence."""
    _patch_extraction(mocker)
    adapter = mocker.patch("app.ai.local_inference.build_local_adapter")
    service = ResumeService(db_session=db_session_mock)

    with pytest.raises(ResumeJobDescriptionError) as exc:
        await service.analyze_resume(
            file_bytes=b"%PDF-fake",
            file_name="cv.pdf",
            content_type="application/pdf",
            target_role="Backend Engineer",
            job_description="   \n",
            user_id=UUID("00000000-0000-0000-0000-000000000001"),
        )

    assert exc.value.code == "job_description_required"
    adapter.assert_not_called()
    db_session_mock.add.assert_not_called()


def test_missing_job_description_returns_422(mocker: MockerFixture) -> None:
    """The analyze route requires a job_description form field."""
    mocker.patch(
        "app.services.resume_service._extract_text_from_pdf",
        return_value=SAMPLE_RESUME,
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/resume/analyze",
            files={"file": ("cv.pdf", b"%PDF-fake", "application/pdf")},
            data={"target_role": "Backend Engineer"},
            headers=_auth_headers(),
        )

    assert response.status_code == 422


def test_require_local_model_file_rejects_urls() -> None:
    """Remote URLs are never treated as local weight files."""
    with pytest.raises(LocalModelNotFoundError):
        require_local_model_file("https://example.com/model.gguf")


@pytest.mark.asyncio
async def test_llama_adapter_complete_does_not_import_llama_when_file_missing(
    tmp_path: Path,
) -> None:
    """LlamaCppAdapter.complete checks the file before importing llama_cpp."""
    missing = tmp_path / "absent.gguf"
    adapter = LlamaCppAdapter(
        model_path=missing,
        n_ctx=512,
        max_tokens=16,
        temperature=0.0,
        timeout_seconds=5,
    )
    with pytest.raises(LocalModelNotFoundError):
        await adapter.complete("prompt")
    assert "llama_cpp" not in sys.modules
