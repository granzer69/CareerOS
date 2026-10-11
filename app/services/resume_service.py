from __future__ import annotations

import io
import logging
from typing import Any
from uuid import UUID

from docx import Document as DocxDocument
from PyPDF2 import PdfReader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.local_inference import LocalInferenceError, LocalModelNotFoundError
from app.ai.resume_analyzer import analyze_resume_text
from app.core.errors import DomainError
from app.models.resume_analysis import ResumeAnalysis
from app.schemas.resume_analysis import ResumeAnalysisRead, ResumeAnalysisSummary

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_BYTES: int = 5 * 1024 * 1024  # 5 MB
ALLOWED_CONTENT_TYPES: dict[str, str] = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}


class ResumeFileTooLargeError(DomainError):
    """Raised when the uploaded file exceeds the 5 MB limit."""


class ResumeUnsupportedTypeError(DomainError):
    """Raised when the uploaded file is not PDF or DOCX."""


class ResumeExtractionError(DomainError):
    """Raised when text extraction from the file fails."""


class ResumeAnalysisFailedError(DomainError):
    """Raised when local model output is not valid analysis JSON."""


class ResumeModelUnavailableError(DomainError):
    """Raised when local model weights are missing."""


class ResumeInferenceFailedError(DomainError):
    """Raised when local inference fails after the weight file was found."""


class ResumeAnalysisNotFoundError(DomainError):
    """Raised when an analysis is missing or not owned by the caller."""


def _extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract plain text from a PDF file's bytes."""
    reader = PdfReader(io.BytesIO(file_bytes))
    pages: list[str] = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    return "\n".join(pages)


def _extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract plain text from a DOCX file's bytes."""
    doc = DocxDocument(io.BytesIO(file_bytes))
    paragraphs: list[str] = []
    for paragraph in doc.paragraphs:
        if paragraph.text.strip():
            paragraphs.append(paragraph.text)
    return "\n".join(paragraphs)


class ResumeService:
    def __init__(self, db_session: AsyncSession) -> None:
        self._db_session = db_session

    async def analyze_resume(
        self,
        *,
        file_bytes: bytes,
        file_name: str,
        content_type: str,
        target_role: str,
        user_id: UUID,
    ) -> ResumeAnalysisRead:
        """
        Parse an uploaded resume file, analyze it with the local model adapter,
        validate the response, persist the result under user_id, and return it.

        Ownership is taken from the authenticated user id, never from the request body.

        Raises:
            ResumeFileTooLargeError: File exceeds 5 MB.
            ResumeUnsupportedTypeError: File is not PDF or DOCX.
            ResumeExtractionError: Text extraction failed.
            ResumeModelUnavailableError: Local weights are missing.
            ResumeInferenceFailedError: Local generation failed.
            ResumeAnalysisFailedError: Model returned invalid JSON after retries.
        """
        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            raise ResumeFileTooLargeError(
                detail=f"File exceeds maximum size of {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB",
                code="file_too_large",
                http_status=413,
            )

        file_format = ALLOWED_CONTENT_TYPES.get(content_type)
        if file_format is None:
            raise ResumeUnsupportedTypeError(
                detail=f"Unsupported file type: {content_type}. Only PDF and DOCX are accepted.",
                code="unsupported_media_type",
                http_status=415,
            )

        try:
            if file_format == "pdf":
                resume_text = _extract_text_from_pdf(file_bytes)
            else:
                resume_text = _extract_text_from_docx(file_bytes)
        except Exception as exc:
            raise ResumeExtractionError(
                detail=f"Failed to extract text from {file_format.upper()} file: {exc}",
                code="extraction_failed",
                http_status=422,
            ) from exc

        if not resume_text.strip():
            raise ResumeExtractionError(
                detail="No readable text found in the uploaded file",
                code="empty_resume",
                http_status=422,
            )

        try:
            analysis_result = await analyze_resume_text(
                resume_text=resume_text,
                target_role=target_role,
            )
        except LocalModelNotFoundError as exc:
            logger.exception("Local model weights are not available")
            raise ResumeModelUnavailableError(
                detail="Local model weights are not available",
                code="model_unavailable",
                http_status=503,
            ) from exc
        except LocalInferenceError as exc:
            logger.exception("Local inference failed")
            raise ResumeInferenceFailedError(
                detail="Local inference failed",
                code="inference_failed",
                http_status=503,
            ) from exc
        except ValueError as exc:
            raise ResumeAnalysisFailedError(
                detail="Model output was not valid analysis JSON",
                code="analysis_failed",
                http_status=422,
            ) from exc

        result_dict: dict[str, Any] = analysis_result.model_dump()

        record = ResumeAnalysis(
            user_id=user_id,
            file_name=file_name,
            target_role=target_role,
            resume_text=resume_text,
            overall_score=result_dict["overall_score"],
            grade=result_dict["grade"],
            ats_score=result_dict["ats_score"],
            estimated_level=result_dict["estimated_level"],
            top_strengths=result_dict["top_strengths"],
            critical_weaknesses=result_dict["critical_weaknesses"],
            keywords_missing=result_dict["keywords_missing"],
            sections=result_dict["sections"],
        )
        self._db_session.add(record)
        await self._db_session.commit()
        await self._db_session.refresh(record)

        return ResumeAnalysisRead.model_validate(record)

    async def list_analyses_for_user(self, *, user_id: UUID) -> list[ResumeAnalysisSummary]:
        """Return the caller's analyses, newest first. Legacy unowned rows are excluded."""
        stmt = (
            select(ResumeAnalysis)
            .where(ResumeAnalysis.user_id == user_id)
            .order_by(ResumeAnalysis.created_at.desc())
            .limit(100)
        )
        result = await self._db_session.execute(stmt)
        rows = result.scalars().all()
        return [ResumeAnalysisSummary.model_validate(row) for row in rows]

    async def get_analysis_for_user(
        self,
        *,
        user_id: UUID,
        analysis_id: UUID,
    ) -> ResumeAnalysisRead:
        """
        Return one owned analysis.

        Missing rows and another user's rows both raise the same not_found error.
        """
        stmt = select(ResumeAnalysis).where(
            ResumeAnalysis.id == analysis_id,
            ResumeAnalysis.user_id == user_id,
        )
        result = await self._db_session.execute(stmt)
        record = result.scalar_one_or_none()
        if record is None:
            raise ResumeAnalysisNotFoundError(
                detail="Analysis not found",
                code="not_found",
                http_status=404,
            )
        return ResumeAnalysisRead.model_validate(record)
