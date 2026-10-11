from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any
from pathlib import Path
from uuid import uuid4

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
from app.services.resume_service import ResumeAnalysisFailedError, ResumeService
from app.core.config import settings
from app.main import app
from app.schemas.resume_analysis import ResumeAnalysisRead

VALID_ANALYSIS: dict[str, Any] = {
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
}


class FakeAdapter:
    def __init__(self, payload: str) -> None:
        self._payload = payload

    async def complete(self, prompt: str) -> str:
        return self._payload


class RaisingAdapter:
    def __init__(self, exc: BaseException) -> None:
        self._exc = exc

    async def complete(self, prompt: str) -> str:
        raise self._exc


def _patch_extraction(mocker: MockerFixture) -> None:
    mocker.patch(
        "app.services.resume_service._extract_text_from_pdf",
        return_value="Python engineer with FastAPI experience at Acme.",
    )


async def _assign_persisted_fields(record: object) -> None:
    record.id = uuid4()  # type: ignore[attr-defined]
    record.session_id = uuid4()  # type: ignore[attr-defined]
    record.created_at = datetime.now(timezone.utc)  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_mocked_adapter_returns_resume_analysis_read_shape(
    db_session_mock: AsyncSession,
    mocker: MockerFixture,
) -> None:
    """A mocked local completion persists and returns the existing ResumeAnalysisRead contract."""
    _patch_extraction(mocker)
    mocker.patch(
        "app.ai.resume_analyzer.build_local_adapter",
        return_value=FakeAdapter(json.dumps(VALID_ANALYSIS)),
    )
    db_session_mock.refresh.side_effect = _assign_persisted_fields

    service = ResumeService(db_session=db_session_mock)
    result = await service.analyze_resume(
        file_bytes=b"%PDF-fake",
        file_name="cv.pdf",
        content_type="application/pdf",
        target_role="Backend Engineer",
    )

    assert isinstance(result, ResumeAnalysisRead)
    assert set(result.model_dump().keys()) == RESUME_READ_FIELDS
    assert result.overall_score == VALID_ANALYSIS["overall_score"]
    assert result.grade == VALID_ANALYSIS["grade"]
    db_session_mock.add.assert_called_once()
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
            data={"target_role": "Backend Engineer"},
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
        "app.ai.resume_analyzer.build_local_adapter",
        return_value=RaisingAdapter(RuntimeError("prompt-secret")),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/resume/analyze",
            files={"file": ("cv.pdf", b"%PDF-fake", "application/pdf")},
            data={"target_role": "Backend Engineer"},
        )

    assert response.status_code == 503
    body = response.json()
    assert body["detail"]["code"] == "inference_failed"
    assert body["detail"]["detail"] == "Local inference failed"
    assert "prompt-secret" not in response.text


@pytest.mark.asyncio
async def test_invalid_json_does_not_persist(
    db_session_mock: AsyncSession,
    mocker: MockerFixture,
) -> None:
    """Malformed model JSON returns analysis_failed and does not commit a row."""
    _patch_extraction(mocker)
    mocker.patch(
        "app.ai.resume_analyzer.build_local_adapter",
        return_value=FakeAdapter("not-json"),
    )

    service = ResumeService(db_session=db_session_mock)
    with pytest.raises(ResumeAnalysisFailedError) as exc:
        await service.analyze_resume(
            file_bytes=b"%PDF-fake",
            file_name="cv.pdf",
            content_type="application/pdf",
            target_role="Backend Engineer",
        )

    assert exc.value.code == "analysis_failed"
    db_session_mock.add.assert_not_called()
    db_session_mock.commit.assert_not_awaited()


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
