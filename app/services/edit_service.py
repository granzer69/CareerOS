from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.local_inference import LocalInferenceError, LocalModelNotFoundError
from app.ai.resume_editor import propose_edits_with_model
from app.core.errors import DomainError
from app.models.resume_analysis import ResumeAnalysis
from app.models.resume_edit import ResumeEdit, ResumeEditBatch, ResumeVersion
from app.schemas.evidence import ModelRequirement, RequirementMatch
from app.schemas.resume_edit import ResumeEditRead, ResumeVersionRead, ResumeVersionSummary
from app.services.edit_grounding import (
    apply_span_at,
    classify_proposal,
    content_hash,
    missing_qualification_proposals,
    resolve_span_conflicts,
)
from app.services.evidence_matcher import match_requirements
from app.services.jd_extraction import extract_requirements
from app.services.resume_service import (
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


class ResumeEditJsonError(DomainError):
    """Raised when local-model edit JSON is invalid after retries."""


class ResumeEditConflictError(DomainError):
    """Raised when the source version changed or a version-number collision occurred."""


class ResumeVersionNotFoundError(DomainError):
    """Raised when a resume version is missing or not owned by the caller."""


def _requirements_from_analysis(analysis: ResumeAnalysis) -> list[ModelRequirement]:
    raw = analysis.requirement_matches or []
    if raw:
        matches = [RequirementMatch.model_validate(item) for item in raw]
        return [
            ModelRequirement(
                text=match.text,
                importance=match.importance,
                category=match.category,
                is_eligibility=match.is_eligibility,
            )
            for match in matches
        ]
    return extract_requirements(analysis.job_description or "")


def matches_for_resume_text(analysis: ResumeAnalysis, resume_text: str) -> list[RequirementMatch]:
    """Rematch stored JD requirements against a specific resume snapshot."""
    return match_requirements(_requirements_from_analysis(analysis), resume_text)


def rescore_resume_text(*, analysis: ResumeAnalysis, resume_text: str) -> ScoredApplication:
    """Recompute rubric v1.0.0 scores for a working copy. The model does not participate."""
    matches = matches_for_resume_text(analysis, resume_text)
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
        source_version_id: UUID | None = None,
    ) -> list[ResumeEditRead]:
        """
        Propose a new reviewable batch from the selected current resume version.

        Existing pending suggestions are preserved. Original analysis text is not modified.
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

        head = await self._require_head_source(
            user_id=user_id,
            analysis=analysis,
            source_version_id=source_version_id,
        )
        matches = matches_for_resume_text(analysis, head["resume_text"])
        try:
            modeled = await propose_edits_with_model(
                resume_text=head["resume_text"],
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
            raise ResumeEditJsonError(
                detail="Model output was not valid edit JSON",
                code="edit_json_invalid",
                http_status=422,
            ) from exc

        classified = [
            classify_proposal(item, resume_text=head["resume_text"], matches=matches)
            for item in modeled.proposals
        ]
        classified = resolve_span_conflicts(classified)
        existing_missing = {
            item.requirement_id for item in classified if item.kind == "missing_qualification"
        }
        for missing in missing_qualification_proposals(matches):
            if missing.requirement_id in existing_missing:
                continue
            classified.append(missing)
            existing_missing.add(missing.requirement_id)

        batch = ResumeEditBatch(
            id=uuid4(),
            analysis_id=analysis_id,
            user_id=user_id,
            source_version_id=head["version_id"],
            source_version_number=head["version_number"],
            source_content_hash=head["content_hash"],
        )
        self._db_session.add(batch)

        records: list[ResumeEdit] = []
        for item in classified:
            record = ResumeEdit(
                analysis_id=analysis_id,
                user_id=user_id,
                batch_id=batch.id,
                source_version_id=head["version_id"],
                source_version_number=head["version_number"],
                source_content_hash=head["content_hash"],
                kind=item.kind,
                status="pending",
                original_span=item.original_span,
                proposed_text=item.proposed_text,
                evidence_span=item.evidence_span,
                requirement_id=item.requirement_id,
                rationale=item.rationale,
                span_start=item.span_start,
                span_end=item.span_end,
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
            .limit(200)
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

        The original analysis resume_text and scores are left unchanged. Stale source
        hashes return 409 instead of patching the wrong snapshot.
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
        if (
            record.kind != "supported_rewrite"
            or not record.original_span
            or record.span_start is None
            or record.span_end is None
        ):
            raise ResumeEditNotAcceptableError(
                detail="Only supported rewrites with identifiable source evidence can be applied",
                code="edit_not_acceptable",
                http_status=422,
            )

        head = await self._head_source(user_id=user_id, analysis=analysis)
        if record.source_content_hash != head["content_hash"] or record.source_version_number != head["version_number"]:
            raise ResumeEditConflictError(
                detail="Edit was generated against a resume version that is no longer current",
                code="edit_source_stale",
                http_status=409,
            )
        try:
            new_text = apply_span_at(
                resume_text=head["resume_text"],
                start=record.span_start,
                end=record.span_end,
                expected_span=record.original_span,
                proposed_text=record.proposed_text,
            )
        except ValueError as exc:
            raise ResumeEditConflictError(
                detail="Edit span no longer matches the current resume version",
                code="edit_source_stale",
                http_status=409,
            ) from exc

        applied = list(head["applied_edit_ids"])
        applied.append(str(record.id))
        record.status = "accepted"
        record.reviewed_at = datetime.now(timezone.utc)
        return await self._commit_new_version(
            analysis=analysis,
            user_id=user_id,
            resume_text=new_text,
            applied_edit_ids=applied,
            next_version_number=head["version_number"] + 1,
        )

    async def restore_version(
        self,
        *,
        user_id: UUID,
        analysis_id: UUID,
        version_id: UUID,
    ) -> ResumeVersionRead:
        """Create a new version that copies an earlier snapshot. History is not rewritten."""
        analysis = await self._resumes.get_owned_analysis_record(
            user_id=user_id,
            analysis_id=analysis_id,
        )
        source = await self._owned_version(
            user_id=user_id,
            analysis_id=analysis_id,
            version_id=version_id,
        )
        head = await self._head_source(user_id=user_id, analysis=analysis)
        return await self._commit_new_version(
            analysis=analysis,
            user_id=user_id,
            resume_text=source.resume_text,
            applied_edit_ids=[f"restore:{source.id}"],
            next_version_number=head["version_number"] + 1,
        )

    async def restore_original(
        self,
        *,
        user_id: UUID,
        analysis_id: UUID,
    ) -> ResumeVersionRead:
        """Create a new version from the immutable original analysis resume_text."""
        analysis = await self._resumes.get_owned_analysis_record(
            user_id=user_id,
            analysis_id=analysis_id,
        )
        head = await self._head_source(user_id=user_id, analysis=analysis)
        return await self._commit_new_version(
            analysis=analysis,
            user_id=user_id,
            resume_text=analysis.resume_text,
            applied_edit_ids=["restore:original"],
            next_version_number=head["version_number"] + 1,
        )

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
        record = await self._owned_version(
            user_id=user_id,
            analysis_id=analysis_id,
            version_id=version_id,
        )
        return ResumeVersionRead.model_validate(record)

    async def _commit_new_version(
        self,
        *,
        analysis: ResumeAnalysis,
        user_id: UUID,
        resume_text: str,
        applied_edit_ids: list[str],
        next_version_number: int,
    ) -> ResumeVersionRead:
        scored = rescore_resume_text(analysis=analysis, resume_text=resume_text)
        version = ResumeVersion(
            analysis_id=analysis.id,
            user_id=user_id,
            version_number=next_version_number,
            resume_text=resume_text,
            content_hash=content_hash(resume_text),
            applied_edit_ids=applied_edit_ids,
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
        self._db_session.add(version)
        try:
            await self._db_session.commit()
        except IntegrityError as exc:
            await self._db_session.rollback()
            raise ResumeEditConflictError(
                detail="A concurrent accept already created this version number",
                code="version_conflict",
                http_status=409,
            ) from exc
        await self._db_session.refresh(version)
        return ResumeVersionRead.model_validate(version)

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

    async def _owned_version(
        self,
        *,
        user_id: UUID,
        analysis_id: UUID,
        version_id: UUID,
    ) -> ResumeVersion:
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

    async def _head_source(
        self,
        *,
        user_id: UUID,
        analysis: ResumeAnalysis,
    ) -> dict[str, object]:
        latest = await self._latest_version(user_id=user_id, analysis_id=analysis.id)
        if latest is not None:
            text = latest.resume_text
            return {
                "resume_text": text,
                "version_id": latest.id,
                "version_number": latest.version_number,
                "content_hash": latest.content_hash or content_hash(text),
                "applied_edit_ids": list(latest.applied_edit_ids or []),
            }
        text = analysis.resume_text
        return {
            "resume_text": text,
            "version_id": None,
            "version_number": 0,
            "content_hash": content_hash(text),
            "applied_edit_ids": [],
        }

    async def _require_head_source(
        self,
        *,
        user_id: UUID,
        analysis: ResumeAnalysis,
        source_version_id: UUID | None,
    ) -> dict[str, object]:
        head = await self._head_source(user_id=user_id, analysis=analysis)
        if source_version_id is None:
            return head
        selected = await self._owned_version(
            user_id=user_id,
            analysis_id=analysis.id,
            version_id=source_version_id,
        )
        if head["version_id"] != selected.id:
            raise ResumeEditConflictError(
                detail="Edits can only be generated against the current resume version",
                code="edit_source_not_current",
                http_status=409,
            )
        return head
