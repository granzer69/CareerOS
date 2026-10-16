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
from app.models.resume_edit import ResumeEdit, ResumeVersion
from app.models.user_profile import UserProfile
from app.schemas.analytics import (
    AnalyticsRead,
    EditKindCount,
    EditStats,
    EligibilityRollup,
    EvidenceBucket,
    ImportanceEvidenceBucket,
    ProfileSkillCoverage,
    RequirementHeatCell,
    RoleBreakdown,
    RoleCoverageRow,
    ScorePoint,
    TermCount,
    VersionDelta,
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
HEATMAP_CELL_LIMIT: int = 48
ROLE_MATRIX_ROWS_PER_ROLE: int = 10
IMPORTANCE_LEVELS: tuple[str, ...] = ("mandatory", "preferred", "contextual")

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

    async def get_analytics_for_user(
        self,
        *,
        user_id: UUID,
        target_role: str | None = None,
    ) -> AnalyticsRead:
        """
        Aggregate the caller's analyses into owner-scoped analytics.

        Uses the same owner filter and 100-row cap as history. Omits resume
        text and does not mix in other users' rows. Optional target_role
        filters the in-memory window before aggregates are computed.
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
        if target_role is not None:
            trimmed = target_role.strip()
            if trimmed:
                rows = [row for row in rows if getattr(row, "target_role", "") == trimmed]

        analysis_ids = [row.id for row in rows]
        edit_rows: list[ResumeEdit] = []
        version_rows: list[ResumeVersion] = []
        if analysis_ids:
            edit_stmt = select(ResumeEdit).where(
                ResumeEdit.user_id == user_id,
                ResumeEdit.analysis_id.in_(analysis_ids),
            )
            version_stmt = select(ResumeVersion).where(
                ResumeVersion.user_id == user_id,
                ResumeVersion.analysis_id.in_(analysis_ids),
            )
            edit_result = await self._db_session.execute(edit_stmt)
            version_result = await self._db_session.execute(version_stmt)
            edit_rows = list(edit_result.scalars().all())
            version_rows = list(version_result.scalars().all())

        profile_skills: list[str] = []
        profile_stmt = select(UserProfile).where(UserProfile.user_id == user_id)
        try:
            profile_result = await self._db_session.execute(profile_stmt)
            profile = profile_result.scalar_one_or_none()
            if profile is not None and isinstance(profile.skills, list):
                profile_skills = [str(skill) for skill in profile.skills if str(skill).strip()]
        except (OperationalError, ProgrammingError) as exc:
            _raise_if_schema_outdated(exc)
            raise

        return build_analytics(
            rows,
            edits=edit_rows,
            versions=version_rows,
            profile_skills=profile_skills,
        )


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


def _as_eligibility_dicts(value: object) -> list[dict[str, object]]:
    """Return eligibility rows as dicts, ignoring malformed entries."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


ELIGIBILITY_STATUSES: tuple[str, ...] = (
    "confirmed_met",
    "confirmed_not_met",
    "unknown",
    "not_applicable",
)


def _normalize_skill_token(skill: str) -> str:
    return " ".join(skill.strip().lower().split())


def _skill_mentions_requirement(skill: str, requirement_text: str) -> bool:
    """Substring match between a profile skill and a JD requirement line."""
    normalized_skill = _normalize_skill_token(skill)
    normalized_requirement = _normalize_skill_token(requirement_text)
    if len(normalized_skill) < 2 or len(normalized_requirement) < 2:
        return False
    return (
        normalized_skill in normalized_requirement
        or normalized_requirement in normalized_skill
    )


def _build_eligibility_rollups(rows: list[object]) -> list[EligibilityRollup]:
    """Aggregate eligibility items by constraint text across analyses."""
    rollups: dict[str, dict[str, int]] = defaultdict(
        lambda: {status: 0 for status in ELIGIBILITY_STATUSES}
    )
    for row in rows:
        for item in _as_eligibility_dicts(getattr(row, "eligibility", None)):
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            status = str(item.get("status", "unknown"))
            if status not in ELIGIBILITY_STATUSES:
                status = "unknown"
            rollups[text][status] += 1
    return [
        EligibilityRollup(
            text=text,
            confirmed_met=counts["confirmed_met"],
            confirmed_not_met=counts["confirmed_not_met"],
            unknown=counts["unknown"],
            not_applicable=counts["not_applicable"],
        )
        for text, counts in sorted(rollups.items(), key=lambda item: item[0].lower())
    ]


def _build_profile_skill_coverage(
    rows: list[object],
    profile_skills: list[str],
) -> list[ProfileSkillCoverage]:
    """
    Count JD requirement rows whose text mentions each profile skill string.

    Does not infer skills that never appear on a posting in this window.
    """
    seen_skills: list[str] = []
    for skill in profile_skills:
        cleaned = skill.strip()
        if cleaned and cleaned not in seen_skills:
            seen_skills.append(cleaned)
    if not seen_skills:
        return []

    counters: dict[str, Counter[str]] = {
        skill: Counter({state: 0 for state in EVIDENCE_STATES}) for skill in seen_skills
    }
    mention_totals: Counter[str] = Counter()

    for row in rows:
        for match in _as_match_dicts(getattr(row, "requirement_matches", None)):
            requirement_text = str(match.get("text", ""))
            state = _evidence_state(match.get("evidence_state"))
            for skill in seen_skills:
                if _skill_mentions_requirement(skill, requirement_text):
                    counters[skill][state] += 1
                    mention_totals[skill] += 1

    return [
        ProfileSkillCoverage(
            skill=skill,
            requirement_mentions=mention_totals[skill],
            confirmed=counters[skill]["confirmed"],
            partial=counters[skill]["partial"],
            not_found=counters[skill]["not_found"],
            contradicted=counters[skill]["contradicted"],
            unknown=counters[skill]["unknown"],
        )
        for skill in seen_skills
    ]


def _evidence_state(value: object) -> str:
    """Map a stored evidence_state onto the known bucket set."""
    if isinstance(value, str) and value in EVIDENCE_STATES:
        return value
    return "unknown"


def _empty_edit_stats() -> EditStats:
    return EditStats(
        total_edits=0,
        pending=0,
        accepted=0,
        rejected=0,
        supported_rewrite_generated=0,
        supported_rewrite_accepted=0,
        supported_rewrite_rejected=0,
        supported_rewrite_accept_rate=None,
    )


def _build_edit_stats(edits: list[object]) -> tuple[EditStats, list[EditKindCount]]:
    """Summarize owned edit rows for funnel metrics."""
    kind_counter: Counter[str] = Counter()
    pending = 0
    accepted = 0
    rejected = 0
    supported_generated = 0
    supported_accepted = 0
    supported_rejected = 0
    for edit in edits:
        kind = str(getattr(edit, "kind", "unknown"))
        status = str(getattr(edit, "status", "pending"))
        kind_counter[kind] += 1
        if status == "pending":
            pending += 1
        elif status == "accepted":
            accepted += 1
        elif status == "rejected":
            rejected += 1
        if kind == "supported_rewrite":
            supported_generated += 1
            if status == "accepted":
                supported_accepted += 1
            elif status == "rejected":
                supported_rejected += 1
    reviewed_supported = supported_accepted + supported_rejected
    accept_rate = (
        round(supported_accepted / reviewed_supported, 3) if reviewed_supported > 0 else None
    )
    stats = EditStats(
        total_edits=len(edits),
        pending=pending,
        accepted=accepted,
        rejected=rejected,
        supported_rewrite_generated=supported_generated,
        supported_rewrite_accepted=supported_accepted,
        supported_rewrite_rejected=supported_rejected,
        supported_rewrite_accept_rate=accept_rate,
    )
    kinds = [
        EditKindCount(kind=kind, count=count)
        for kind, count in sorted(kind_counter.items(), key=lambda item: (-item[1], item[0]))
    ]
    return stats, kinds


def _int_score(row: object, field: str) -> int | None:
    value = getattr(row, field, None)
    return value if isinstance(value, int) else None


def _readiness_score(row: object) -> int | None:
    readiness = _int_score(row, "application_readiness_score")
    if readiness is not None:
        return readiness
    return _int_score(row, "overall_score")


def _build_version_deltas(rows: list[object], versions: list[object]) -> list[VersionDelta]:
    """Compare original analysis readiness to the latest accepted version."""
    row_by_id = {getattr(row, "id"): row for row in rows}
    by_analysis: dict[object, list[object]] = defaultdict(list)
    for version in versions:
        by_analysis[getattr(version, "analysis_id")].append(version)
    deltas: list[VersionDelta] = []
    for analysis_id, version_list in by_analysis.items():
        row = row_by_id.get(analysis_id)
        if row is None or not version_list:
            continue
        latest = max(version_list, key=lambda item: int(getattr(item, "version_number", 0)))
        original = _readiness_score(row)
        latest_readiness = _readiness_score(latest)
        delta: int | None = None
        if original is not None and latest_readiness is not None:
            delta = latest_readiness - original
        deltas.append(
            VersionDelta(
                analysis_id=analysis_id,
                file_name=str(getattr(row, "file_name", "")),
                target_role=str(getattr(row, "target_role", "")),
                original_readiness=original,
                latest_version_readiness=latest_readiness,
                delta=delta,
                latest_version_number=int(getattr(latest, "version_number", 0)),
                rubric_version=getattr(latest, "rubric_version", None),
                original_job_fit=_int_score(row, "job_fit_score"),
                latest_job_fit=_int_score(latest, "job_fit_score"),
                original_alignment=_int_score(row, "resume_alignment_score"),
                latest_alignment=_int_score(latest, "resume_alignment_score"),
                original_terminology=_int_score(row, "ats_score"),
                latest_terminology=_int_score(latest, "ats_score"),
            )
        )
    return sorted(deltas, key=lambda item: item.file_name.lower())


def _build_requirement_heatmap(rows: list[object]) -> list[RequirementHeatCell]:
    """Top requirement × role × evidence_state cells from stored matches."""
    cell_counter: Counter[tuple[str, str, str]] = Counter()
    for row in rows:
        role = str(getattr(row, "target_role", "") or "Unknown")
        for match in _as_match_dicts(getattr(row, "requirement_matches", None)):
            text = match.get("text")
            if not isinstance(text, str):
                continue
            requirement = text.strip()[:120]
            if not requirement:
                continue
            state = _evidence_state(match.get("evidence_state"))
            cell_counter[(requirement, role, state)] += 1
    return [
        RequirementHeatCell(
            requirement_text=key[0],
            target_role=key[1],
            evidence_state=key[2],
            count=count,
        )
        for key, count in sorted(cell_counter.items(), key=lambda item: (-item[1], item[0]))[
            :HEATMAP_CELL_LIMIT
        ]
    ]


def _normalize_importance(value: object) -> str:
    if isinstance(value, str) and value in IMPORTANCE_LEVELS:
        return value
    return "contextual"


def _build_importance_evidence(
    importance_counter: Counter[tuple[str, str]],
) -> list[ImportanceEvidenceBucket]:
    """Flatten importance × evidence counts in stable order."""
    buckets: list[ImportanceEvidenceBucket] = []
    for importance in IMPORTANCE_LEVELS:
        for state in EVIDENCE_STATES:
            count = importance_counter[(importance, state)]
            if count:
                buckets.append(
                    ImportanceEvidenceBucket(importance=importance, state=state, count=count)
                )
    return buckets


def _build_role_coverage_matrix(rows: list[object]) -> list[RoleCoverageRow]:
    """Matrix rows: per target_role, top requirements with state counts."""
    matrix: dict[tuple[str, str], Counter[str]] = defaultdict(
        lambda: Counter({state: 0 for state in EVIDENCE_STATES})
    )
    for row in rows:
        role = str(getattr(row, "target_role", "") or "Unknown")
        for match in _as_match_dicts(getattr(row, "requirement_matches", None)):
            text = match.get("text")
            if not isinstance(text, str):
                continue
            requirement = text.strip()[:120]
            if not requirement:
                continue
            state = _evidence_state(match.get("evidence_state"))
            matrix[(role, requirement)][state] += 1
    by_role: dict[str, list[tuple[str, Counter[str], int]]] = defaultdict(list)
    for (role, requirement), states in matrix.items():
        total = sum(states.values())
        by_role[role].append((requirement, states, total))
    output: list[RoleCoverageRow] = []
    for role in sorted(by_role.keys()):
        ranked = sorted(by_role[role], key=lambda item: (-item[2], item[0]))[:ROLE_MATRIX_ROWS_PER_ROLE]
        for requirement, states, _total in ranked:
            output.append(
                RoleCoverageRow(
                    target_role=role,
                    requirement_text=requirement,
                    confirmed=states["confirmed"],
                    partial=states["partial"],
                    not_found=states["not_found"],
                    contradicted=states["contradicted"],
                    unknown=states["unknown"],
                )
            )
    return output


def build_analytics(
    rows: list[object],
    *,
    edits: list[object] | None = None,
    versions: list[object] | None = None,
    profile_skills: list[str] | None = None,
) -> AnalyticsRead:
    """
    Fold owned analysis rows into AnalyticsRead.

    Score trends are oldest-first. Null rubric scores stay null — they are
    not coerced to zero. Resume text is never copied onto the payload.
    """
    evidence_counts: Counter[str] = Counter({state: 0 for state in EVIDENCE_STATES})
    importance_counter: Counter[tuple[str, str]] = Counter()
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
            importance = _normalize_importance(match.get("importance"))
            importance_counter[(importance, state)] += 1
            if state in stats:
                stats[state] = int(stats[state]) + 1
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
            ats_score=_int_score(row, "ats_score"),
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
    edit_stats, edit_kinds = (
        _build_edit_stats(edits) if edits else (_empty_edit_stats(), [])
    )
    version_deltas = _build_version_deltas(rows, versions or [])
    requirement_heatmap = _build_requirement_heatmap(rows)
    importance_evidence = _build_importance_evidence(importance_counter)
    role_coverage_matrix = _build_role_coverage_matrix(rows)
    eligibility_rollups = _build_eligibility_rollups(rows)
    profile_skill_coverage = _build_profile_skill_coverage(rows, profile_skills or [])
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
        edits=edit_stats,
        edit_kinds=edit_kinds,
        version_deltas=version_deltas,
        requirement_heatmap=requirement_heatmap,
        importance_evidence=importance_evidence,
        role_coverage_matrix=role_coverage_matrix,
        eligibility_rollups=eligibility_rollups,
        profile_skill_coverage=profile_skill_coverage,
    )
