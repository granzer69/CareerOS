from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.local_inference import LocalInferenceError, LocalModelNotFoundError
from app.ai.resume_editor import propose_edits_with_model
from app.core.errors import DomainError
from app.models.resume_analysis import ResumeAnalysis
from app.models.resume_edit import ResumeEdit, ResumeVersion
from app.schemas.evidence import ModelRequirement, RequirementMatch
from app.schemas.resume_edit import ResumeEditRead, ResumeVersionRead, ResumeVersionSummary
from app.services.edit_grounding import (
    apply_span_replacement,
    classify_proposal,
    missing_qualification_proposals,
)
from app.services.evidence_matcher import match_requirements
from app.services.jd_extraction import extract_requirements
from app.services.resume_service import (
    ResumeAnalysisFailedError,
    ResumeAnalysisNotFoundError,
    ResumeInferenceFailedError,
    ResumeJobDescriptionError,
    ResumeModelUnavailableError,
    ResumeService,
)
from app.services.scoring import ScoredApplication, score_application

logger = logging.getLogger(__name__)


class ResumeEditNotFoundError(DomainError):
    """Raised when an edit is missing or not owned by the caller."""


class ResumeEditNotAcceptableError(DomainError):
    """Raised when an edit cannot be applied to a working copy."""


class ResumeEditNotPendingError(DomainError):
    """Raised when an edit was already accepted or rejected."""


class ResumeVersionNotFoundError(DomainError):
    """Raised when a resume version is missing or not owned by the caller."""


def _matches_from_analysis(analysis: ResumeAnalysis) -> list[RequirementMatch]:
    raw = analysis.requirement_matches or []
    if raw:
        return [RequirementMatch.model_validate(item) for item in raw]
    job_description = (analysis.job_description or "").strip()
    if not job_description:
        return []
    return match_requirements(extract_requirements(job_description), analysis.resume_text)


def _requirements_from_matches(matches: list[RequirementMatch]) -> list[ModelRequirement]:
    return [
        ModelRequirement(
            text=match.text,
            importance=match.importance,
            category=match.category,
            is_eligibility=match.is_eligibility,
        )
        for match in matches
    ]


def rescore_resume_text(*, analysis: ResumeAnalysis, resume_text: str) -> ScoredApplication:
    """Recompute rubric v1.0.0 scores for a working copy. The model does not participate."""
    source_matches = _matches_from_analysis(analysis)
    if source_matches:
        requirements = _requirements_from_matches(source_matches)
    else:
        requirements = extract_requirements(analysis.job_description or "")
    matches = match_requirements(requirements, resume_text)
    return score_application(
        matches=matches,
        resume_text=resume_text,
        estimated_level_hint=analysis.estimated_level,
    )


class EditService:
    def __init__(self, db_session: AsyncSession) -> None:
        self._db_session = db_session
        self._resumes = ResumeService(db_session=db_session)

    async def generate_edits(
        self,
        *,
        user_id: UUID,
        analysis_id: UUID,
    ) -> list[ResumeEditRead]:
        """
        Propose reviewable edits from resume evidence and the stored job description.

        Model output is schema-validated then classified deterministically. The original
        analysis resume_text is never modified.
        """
        analysis = await self._resumes.get_owned_analysis_record(
            user_id=user_id,
            analysis_id=analysis_id,
        )
        job_description = (analysis.job_description or "").strip()
        if not job_description:
            raise ResumeJobDescriptionError(
                detail="A job description is required",
                code="job_description_required",
                http_status=422,
            )

        matches = _matches_from_analysis(analysis)
        try:
            modeled = await propose_edits_with_model(
                resume_text=analysis.resume_text,
                target_role=analysis.target_role,
                job_description=job_description,
                matches=matches,
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
                detail="Model output was not valid edit JSON",
                code="analysis_failed",
                http_status=422,
            ) from exc

        classified = [
            classify_proposal(item, resume_text=analysis.resume_text, matches=matches)
            for item in modeled.proposals
        ]
        existing_missing = {
            item.requirement_id for item in classified if item.kind == "missing_qualification"
        }
        for missing in missing_qualification_proposals(matches):
            if missing.requirement_id in existing_missing:
                continue
            classified.append(missing)
            existing_missing.add(missing.requirement_id)

        await self._db_session.execute(
            delete(ResumeEdit).where(
                ResumeEdit.analysis_id == analysis_id,
                ResumeEdit.user_id == user_id,
                ResumeEdit.status == "pending",
            )
        )

        records: list[ResumeEdit] = []
        for item in classified:
            record = ResumeEdit(
                analysis_id=analysis_id,
                user_id=user_id,
                kind=item.kind,
                status="pending",
                original_span=item.original_span,
                proposed_text=item.proposed_text,
                evidence_span=item.evidence_span,
                requirement_id=item.requirement_id,
                rationale=item.rationale,
            )
            self._db_session.add(record)
            records.append(record)

        await self._db_session.commit()
        for record in records:
            await self._db_session.refresh(record)
        return [ResumeEditRead.model_validate(record) for record in records]

    async def list_edits(
        self,
        *,
        user_id: UUID,
        analysis_id: UUID,
    ) -> list[ResumeEditRead]:
        """List the caller's edit suggestions for an owned analysis, newest first."""
        await self._resumes.get_owned_analysis_record(
            user_id=user_id,
            analysis_id=analysis_id,
        )
        stmt = (
            select(ResumeEdit)
            .where(
                ResumeEdit.analysis_id == analysis_id,
                ResumeEdit.user_id == user_id,
            )
            .order_by(ResumeEdit.created_at.desc())
            .limit(100)
        )
        result = await self._db_session.execute(stmt)
        rows = result.scalars().all()
        return [ResumeEditRead.model_validate(row) for row in rows]

    async def reject_edit(
        self,
        *,
        user_id: UUID,
        analysis_id: UUID,
        edit_id: UUID,
    ) -> ResumeEditRead:
        """Mark a pending owned suggestion as rejected without changing resume text."""
        record = await self._owned_edit(
            user_id=user_id,
            analysis_id=analysis_id,
            edit_id=edit_id,
        )
        if record.status != "pending":
            raise ResumeEditNotPendingError(
                detail="Edit is not pending",
                code="edit_not_pending",
                http_status=409,
            )
        record.status = "rejected"
        record.reviewed_at = datetime.now(timezone.utc)
        await self._db_session.commit()
        await self._db_session.refresh(record)
        return ResumeEditRead.model_validate(record)

    async def accept_edit(
        self,
        *,
        user_id: UUID,
        analysis_id: UUID,
        edit_id: UUID,
    ) -> ResumeVersionRead:
        """
        Apply one supported rewrite to a new version and re-score with rubric v1.0.0.

        The original analysis resume_text and scores are left unchanged.
        """
        analysis = await self._resumes.get_owned_analysis_record(
            user_id=user_id,
            analysis_id=analysis_id,
        )
        record = await self._owned_edit(
            user_id=user_id,
            analysis_id=analysis_id,
            edit_id=edit_id,
        )
        if record.status != "pending":
            raise ResumeEditNotPendingError(
                detail="Edit is not pending",
                code="edit_not_pending",
                http_status=409,
            )
        if record.kind != "supported_rewrite" or not record.original_span:
            raise ResumeEditNotAcceptableError(
                detail="Only supported rewrites with identifiable source evidence can be applied",
                code="edit_not_acceptable",
                http_status=422,
            )

        latest = await self._latest_version(user_id=user_id, analysis_id=analysis_id)
        base_text = latest.resume_text if latest is not None else analysis.resume_text
        try:
            new_text = apply_span_replacement(
                resume_text=base_text,
                original_span=record.original_span,
                proposed_text=record.proposed_text,
            )
        except ValueError as exc:
            raise ResumeEditNotAcceptableError(
                detail="original_span is not present in the current resume version",
                code="edit_not_applicable",
                http_status=422,
            ) from exc

        scored = rescore_resume_text(analysis=analysis, resume_text=new_text)
        applied = list(latest.applied_edit_ids) if latest is not None else []
        applied.append(str(record.id))
        version = ResumeVersion(
            analysis_id=analysis_id,
            user_id=user_id,
            version_number=(latest.version_number if latest is not None else 0) + 1,
            resume_text=new_text,
            applied_edit_ids=applied,
            overall_score=scored.application_readiness_score,
            grade=scored.grade,
            ats_score=scored.ats_score,
            estimated_level=scored.estimated_level,
            job_fit_score=scored.job_fit_score,
            resume_alignment_score=scored.resume_alignment_score,
            application_readiness_score=scored.application_readiness_score,
            rubric_version=scored.rubric_version,
            requirement_matches=[item.model_dump() for item in scored.requirement_matches],
            eligibility=[item.model_dump() for item in scored.eligibility],
            blocked_by_requirement=scored.blocked_by_requirement,
            completeness_included=scored.completeness_included,
        )
        record.status = "accepted"
        record.reviewed_at = datetime.now(timezone.utc)
        self._db_session.add(version)
        await self._db_session.commit()
        await self._db_session.refresh(version)
        await self._db_session.refresh(record)
        return ResumeVersionRead.model_validate(version)

    async def list_versions(
        self,
        *,
        user_id: UUID,
        analysis_id: UUID,
    ) -> list[ResumeVersionSummary]:
        """List accepted working copies for an owned analysis, newest first."""
        await self._resumes.get_owned_analysis_record(
            user_id=user_id,
            analysis_id=analysis_id,
        )
        stmt = (
            select(ResumeVersion)
            .where(
                ResumeVersion.analysis_id == analysis_id,
                ResumeVersion.user_id == user_id,
            )
            .order_by(ResumeVersion.version_number.desc())
            .limit(100)
        )
        result = await self._db_session.execute(stmt)
        rows = result.scalars().all()
        return [ResumeVersionSummary.model_validate(row) for row in rows]

    async def get_version(
        self,
        *,
        user_id: UUID,
        analysis_id: UUID,
        version_id: UUID,
    ) -> ResumeVersionRead:
        """Return one owned resume version. Cross-user access is the same 404 as missing."""
        await self._resumes.get_owned_analysis_record(
            user_id=user_id,
            analysis_id=analysis_id,
        )
        stmt = select(ResumeVersion).where(
            ResumeVersion.id == version_id,
            ResumeVersion.analysis_id == analysis_id,
            ResumeVersion.user_id == user_id,
        )
        result = await self._db_session.execute(stmt)
        record = result.scalar_one_or_none()
        if record is None:
            raise ResumeVersionNotFoundError(
                detail="Version not found",
                code="not_found",
                http_status=404,
            )
        return ResumeVersionRead.model_validate(record)

    async def _owned_edit(
        self,
        *,
        user_id: UUID,
        analysis_id: UUID,
        edit_id: UUID,
    ) -> ResumeEdit:
        await self._resumes.get_owned_analysis_record(
            user_id=user_id,
            analysis_id=analysis_id,
        )
        stmt = select(ResumeEdit).where(
            ResumeEdit.id == edit_id,
            ResumeEdit.analysis_id == analysis_id,
            ResumeEdit.user_id == user_id,
        )
        result = await self._db_session.execute(stmt)
        record = result.scalar_one_or_none()
        if record is None:
            raise ResumeEditNotFoundError(
                detail="Edit not found",
                code="not_found",
                http_status=404,
            )
        return record

    async def _latest_version(
        self,
        *,
        user_id: UUID,
        analysis_id: UUID,
    ) -> ResumeVersion | None:
        stmt = (
            select(ResumeVersion)
            .where(
                ResumeVersion.analysis_id == analysis_id,
                ResumeVersion.user_id == user_id,
            )
            .order_by(ResumeVersion.version_number.desc())
            .limit(1)
        )
        result = await self._db_session.execute(stmt)
        return result.scalar_one_or_none()
