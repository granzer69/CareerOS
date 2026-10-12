from __future__ import annotations

import io
import logging
from collections import Counter, defaultdict
from uuid import UUID

from docx import Document as DocxDocument
from PyPDF2 import PdfReader
from sqlalchemy import select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.local_inference import LocalInferenceError, LocalModelNotFoundError
from app.ai.resume_analyzer import extract_requirements_with_model
from app.core.errors import DomainError
from app.models.resume_analysis import ResumeAnalysis
from app.schemas.analytics import (
    AnalyticsRead,
    EvidenceBucket,
    RoleBreakdown,
    ScorePoint,
    TermCount,
)
from app.schemas.resume_analysis import ResumeAnalysisRead, ResumeAnalysisSummary
from app.services.evidence_matcher import match_requirements
from app.services.jd_extraction import derive_target_role, extract_requirements, merge_requirements
from app.services.scoring import score_application

logger = logging.getLogger(__name__)

EVIDENCE_STATES: tuple[str, ...] = (
    "confirmed",
    "partial",
    "not_found",
    "contradicted",
    "unknown",
)
MANDATORY_GAP_STATES: frozenset[str] = frozenset({"not_found", "contradicted"})
MISSING_TERM_LIMIT: int = 15

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


class ResumeSchemaOutdatedError(DomainError):
    """Raised when the database is missing required resume_analyses columns."""


def _raise_if_schema_outdated(exc: Exception) -> None:
    """Map missing-column driver errors to an actionable schema_outdated failure."""
    message = str(exc).lower()
    if "no such column" in message or "does not exist" in message:
        raise ResumeSchemaOutdatedError(
            detail=(
                "The database schema is behind Alembic. Stop the API, delete any leftover "
                "local sqlite file, then run `alembic upgrade head`. create_all does not "
                "add columns to existing tables."
            ),
            code="schema_outdated",
            http_status=503,
        ) from exc


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
        try:
            result = await self._db_session.execute(stmt)
        except (OperationalError, ProgrammingError) as exc:
            _raise_if_schema_outdated(exc)
            raise
        rows = result.scalars().all()
        return [ResumeAnalysisSummary.model_validate(row) for row in rows]

    async def get_owned_analysis_record(
        self,
        *,
        user_id: UUID,
        analysis_id: UUID,
    ) -> ResumeAnalysis:
        """
        Return the owned ORM analysis row.

        Missing rows and another user's rows both raise the same not_found error.
        """
        stmt = select(ResumeAnalysis).where(
            ResumeAnalysis.id == analysis_id,
            ResumeAnalysis.user_id == user_id,
        )
        try:
            result = await self._db_session.execute(stmt)
        except (OperationalError, ProgrammingError) as exc:
            _raise_if_schema_outdated(exc)
            raise
        record = result.scalar_one_or_none()
        if record is None:
            raise ResumeAnalysisNotFoundError(
                detail="Analysis not found",
                code="not_found",
                http_status=404,
            )
        return record

    async def get_analysis_for_user(
        self,
        *,
        user_id: UUID,
        analysis_id: UUID,
    ) -> ResumeAnalysisRead:
        """Return one owned analysis without resume_text."""
        record = await self.get_owned_analysis_record(
            user_id=user_id,
            analysis_id=analysis_id,
        )
        return ResumeAnalysisRead.model_validate(record)

    async def get_analytics_for_user(self, *, user_id: UUID) -> AnalyticsRead:
        """
        Aggregate the caller's analyses into owner-scoped analytics.

        Uses the same owner filter and 100-row cap as history. Omits resume
        text and does not mix in other users' rows.
        """
        stmt = (
            select(ResumeAnalysis)
            .where(ResumeAnalysis.user_id == user_id)
            .order_by(ResumeAnalysis.created_at.desc())
            .limit(100)
        )
        try:
            result = await self._db_session.execute(stmt)
        except (OperationalError, ProgrammingError) as exc:
            _raise_if_schema_outdated(exc)
            raise
        rows = list(result.scalars().all())
        return build_analytics(rows)


def _as_match_dicts(value: object) -> list[dict[str, object]]:
    """Return requirement_matches as dict rows, ignoring malformed entries."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _as_terms(value: object) -> list[str]:
    """Return non-empty missing-terminology strings."""
    if not isinstance(value, list):
        return []
    terms: list[str] = []
    for item in value:
        if isinstance(item, str):
            cleaned = item.strip()
            if cleaned:
                terms.append(cleaned)
    return terms


def _evidence_state(value: object) -> str:
    """Map a stored evidence_state onto the known bucket set."""
    if isinstance(value, str) and value in EVIDENCE_STATES:
        return value
    return "unknown"


def build_analytics(rows: list[object]) -> AnalyticsRead:
    """
    Fold owned analysis rows into AnalyticsRead.

    Score trends are oldest-first. Null rubric scores stay null — they are
    not coerced to zero. Resume text is never copied onto the payload.
    """
    evidence_counts: Counter[str] = Counter({state: 0 for state in EVIDENCE_STATES})
    term_counts: Counter[str] = Counter()
    role_stats: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "analysis_count": 0,
            "readiness_sum": 0,
            "readiness_n": 0,
            "confirmed": 0,
            "not_found": 0,
            "contradicted": 0,
        }
    )
    requirement_count = 0
    blocked_count = 0
    mandatory_gap_count = 0
    rubric_versions: list[str] = []
    seen_versions: set[str] = set()

    for row in rows:
        matches = _as_match_dicts(getattr(row, "requirement_matches", None))
        requirement_count += len(matches)
        if bool(getattr(row, "blocked_by_requirement", False)):
            blocked_count += 1
        role = str(getattr(row, "target_role", "") or "Unknown")
        stats = role_stats[role]
        stats["analysis_count"] = int(stats["analysis_count"]) + 1
        readiness = getattr(row, "application_readiness_score", None)
        if isinstance(readiness, int):
            stats["readiness_sum"] = int(stats["readiness_sum"]) + readiness
            stats["readiness_n"] = int(stats["readiness_n"]) + 1
        version = getattr(row, "rubric_version", None)
        if isinstance(version, str) and version and version not in seen_versions:
            seen_versions.add(version)
            rubric_versions.append(version)
        for match in matches:
            state = _evidence_state(match.get("evidence_state"))
            evidence_counts[state] += 1
            if state in stats:
                stats[state] = int(stats[state]) + 1
            importance = match.get("importance")
            if importance == "mandatory" and state in MANDATORY_GAP_STATES:
                mandatory_gap_count += 1
        for term in _as_terms(getattr(row, "keywords_missing", None)):
            term_counts[term] += 1

    newest = rows[0] if rows else None
    scores_oldest_first = list(reversed(rows))
    score_points = [
        ScorePoint(
            id=getattr(row, "id"),
            created_at=getattr(row, "created_at"),
            file_name=getattr(row, "file_name"),
            target_role=getattr(row, "target_role"),
            overall_score=getattr(row, "overall_score", None),
            job_fit_score=getattr(row, "job_fit_score", None),
            resume_alignment_score=getattr(row, "resume_alignment_score", None),
            application_readiness_score=getattr(row, "application_readiness_score", None),
            rubric_version=getattr(row, "rubric_version", None),
            blocked_by_requirement=bool(getattr(row, "blocked_by_requirement", False)),
        )
        for row in scores_oldest_first
    ]
    roles = [
        RoleBreakdown(
            target_role=role,
            analysis_count=int(stats["analysis_count"]),
            avg_readiness=(
                round(int(stats["readiness_sum"]) / int(stats["readiness_n"]), 1)
                if int(stats["readiness_n"]) > 0
                else None
            ),
            confirmed=int(stats["confirmed"]),
            not_found=int(stats["not_found"]),
            contradicted=int(stats["contradicted"]),
        )
        for role, stats in sorted(
            role_stats.items(),
            key=lambda item: (-int(item[1]["analysis_count"]), item[0]),
        )
    ]
    missing_terminology = [
        TermCount(term=term, count=count)
        for term, count in sorted(term_counts.items(), key=lambda item: (-item[1], item[0]))[
            :MISSING_TERM_LIMIT
        ]
    ]
    return AnalyticsRead(
        analysis_count=len(rows),
        requirement_count=requirement_count,
        blocked_count=blocked_count,
        mandatory_gap_count=mandatory_gap_count,
        latest_created_at=getattr(newest, "created_at", None) if newest is not None else None,
        rubric_versions=rubric_versions,
        evidence=[EvidenceBucket(state=state, count=evidence_counts[state]) for state in EVIDENCE_STATES],
        scores=score_points,
        roles=roles,
        missing_terminology=missing_terminology,
    )
