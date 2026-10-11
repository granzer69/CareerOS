from __future__ import annotations

import io
import logging
from uuid import UUID

from docx import Document as DocxDocument
from PyPDF2 import PdfReader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.local_inference import LocalInferenceError, LocalModelNotFoundError
from app.ai.resume_analyzer import extract_requirements_with_model
from app.core.errors import DomainError
from app.models.resume_analysis import ResumeAnalysis
from app.schemas.resume_analysis import ResumeAnalysisRead, ResumeAnalysisSummary
from app.services.evidence_matcher import match_requirements
from app.services.jd_extraction import derive_target_role, extract_requirements, merge_requirements
from app.services.scoring import score_application

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_BYTES: int = 5 * 1024 * 1024  # 5 MB
MAX_JOB_DESCRIPTION_CHARS: int = 20_000
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


class ResumeJobDescriptionError(DomainError):
    """Raised when the job description is missing, empty, or too long."""


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
        job_description: str,
        user_id: UUID,
    ) -> ResumeAnalysisRead:
        """
        Parse a resume, extract JD requirements, match evidence, and persist rubric scores.

        The local model may add structured requirements. Numeric scores always come from
        the versioned rubric. Ownership is taken from the authenticated user id.

        Raises:
            ResumeFileTooLargeError: File exceeds 5 MB.
            ResumeUnsupportedTypeError: File is not PDF or DOCX.
            ResumeExtractionError: Text extraction failed.
            ResumeJobDescriptionError: Job description is empty or too long.
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

        cleaned_jd = job_description.strip()
        if not cleaned_jd:
            raise ResumeJobDescriptionError(
                detail="A job description is required",
                code="job_description_required",
                http_status=422,
            )
        if len(cleaned_jd) > MAX_JOB_DESCRIPTION_CHARS:
            raise ResumeJobDescriptionError(
                detail=f"Job description exceeds {MAX_JOB_DESCRIPTION_CHARS} characters",
                code="job_description_too_long",
                http_status=422,
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

        stored_role = derive_target_role(
            target_role=target_role,
            job_description=cleaned_jd,
        )
        deterministic = extract_requirements(cleaned_jd)

        try:
            modeled = await extract_requirements_with_model(
                resume_text=resume_text,
                target_role=stored_role,
                job_description=cleaned_jd,
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

        merged = merge_requirements(
            deterministic=deterministic,
            modeled=modeled.requirements,
        )
        matches = match_requirements(merged, resume_text)
        scored = score_application(
            matches=matches,
            resume_text=resume_text,
            estimated_level_hint=modeled.estimated_level,
        )

        record = ResumeAnalysis(
            user_id=user_id,
            file_name=file_name,
            target_role=stored_role,
            resume_text=resume_text,
            overall_score=scored.application_readiness_score,
            grade=scored.grade,
            ats_score=scored.ats_score,
            estimated_level=scored.estimated_level,
            top_strengths=scored.top_strengths,
            critical_weaknesses=scored.critical_weaknesses,
            keywords_missing=scored.keywords_missing,
            sections=scored.sections,
            job_description=cleaned_jd,
            job_fit_score=scored.job_fit_score,
            resume_alignment_score=scored.resume_alignment_score,
            application_readiness_score=scored.application_readiness_score,
            rubric_version=scored.rubric_version,
            requirement_matches=[item.model_dump() for item in scored.requirement_matches],
            eligibility=[item.model_dump() for item in scored.eligibility],
            blocked_by_requirement=scored.blocked_by_requirement,
            completeness_included=scored.completeness_included,
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
