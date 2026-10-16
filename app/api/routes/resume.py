from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import DomainError, domain_error_to_http_exception, internal_error_to_http_exception
from app.core.auth import get_current_user_id
from app.core.database import get_db_session
from app.schemas.analytics import AnalyticsRead
from app.schemas.resume_analysis import ResumeAnalysisRead, ResumeAnalysisSummary
from app.schemas.resume_edit import ResumeEditRead, ResumeVersionRead, ResumeVersionSummary
from app.services.edit_service import EditService
from app.services.resume_service import ResumeService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/resume", tags=["resume"])


async def get_resume_service(
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ResumeService:
    return ResumeService(db_session=db_session)


async def get_edit_service(
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> EditService:
    return EditService(db_session=db_session)


@router.post(
    "/analyze",
    response_model=ResumeAnalysisRead,
    status_code=status.HTTP_200_OK,
    summary="Analyze a resume file",
    description=(
        "Upload a PDF or DOCX resume (max 5 MB) with a target role and job description. "
        "Requires a Bearer JWT. Scores come from a versioned rubric, not the local model. "
        "The analysis is stored under the authenticated user."
    ),
)
async def analyze_resume(
    file: UploadFile,
    target_role: Annotated[str, Form(min_length=1, max_length=200)],
    job_description: Annotated[str, Form(min_length=1, max_length=20000)],
    service: Annotated[ResumeService, Depends(get_resume_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> ResumeAnalysisRead:
    try:
        file_bytes = await file.read()
        return await service.analyze_resume(
            file_bytes=file_bytes,
            file_name=file.filename or "unknown",
            content_type=file.content_type or "",
            target_role=target_role,
            job_description=job_description,
            user_id=current_user_id,
        )
    except DomainError as exc:
        raise domain_error_to_http_exception(exc) from exc
    except Exception as exc:
        logger.exception("Resume analysis failed")
        raise internal_error_to_http_exception() from exc


@router.get(
    "/analytics",
    response_model=AnalyticsRead,
    status_code=status.HTTP_200_OK,
    summary="Owner-scoped evidence and score analytics",
    description=(
        "Aggregate the authenticated user's last 100 analyses. Counts evidence "
        "states, mandatory gaps, and score trends. This is not a hiring "
        "probability, company prediction, or cross-user benchmark."
    ),
)
async def get_resume_analytics(
    service: Annotated[ResumeService, Depends(get_resume_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
    target_role: Annotated[str | None, Query(max_length=200)] = None,
) -> AnalyticsRead:
    try:
        return await service.get_analytics_for_user(
            user_id=current_user_id,
            target_role=target_role,
        )
    except DomainError as exc:
        raise domain_error_to_http_exception(exc) from exc
    except Exception as exc:
        logger.exception("Reading resume analytics failed")
        raise internal_error_to_http_exception() from exc


@router.get(
    "/analyses",
    response_model=list[ResumeAnalysisSummary],
    status_code=status.HTTP_200_OK,
    summary="List the current user's resume analyses",
)
async def list_resume_analyses(
    service: Annotated[ResumeService, Depends(get_resume_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> list[ResumeAnalysisSummary]:
    try:
        return await service.list_analyses_for_user(user_id=current_user_id)
    except DomainError as exc:
        raise domain_error_to_http_exception(exc) from exc
    except Exception as exc:
        logger.exception("Listing resume analyses failed")
        raise internal_error_to_http_exception() from exc


@router.get(
    "/analyses/{analysis_id}",
    response_model=ResumeAnalysisRead,
    status_code=status.HTTP_200_OK,
    summary="Read one owned resume analysis",
)
async def get_resume_analysis(
    analysis_id: UUID,
    service: Annotated[ResumeService, Depends(get_resume_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> ResumeAnalysisRead:
    try:
        return await service.get_analysis_for_user(
            user_id=current_user_id,
            analysis_id=analysis_id,
        )
    except DomainError as exc:
        raise domain_error_to_http_exception(exc) from exc
    except Exception as exc:
        logger.exception("Reading resume analysis failed")
        raise internal_error_to_http_exception() from exc


@router.post(
    "/analyses/{analysis_id}/edits",
    response_model=list[ResumeEditRead],
    status_code=status.HTTP_200_OK,
    summary="Propose evidence-grounded resume edits",
)
async def generate_resume_edits(
    analysis_id: UUID,
    service: Annotated[EditService, Depends(get_edit_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
    source_version_id: Annotated[UUID | None, Query()] = None,
) -> list[ResumeEditRead]:
    try:
        return await service.generate_edits(
            user_id=current_user_id,
            analysis_id=analysis_id,
            source_version_id=source_version_id,
        )
    except DomainError as exc:
        raise domain_error_to_http_exception(exc) from exc
    except Exception as exc:
        logger.exception("Generating resume edits failed")
        raise internal_error_to_http_exception() from exc


@router.get(
    "/analyses/{analysis_id}/edits",
    response_model=list[ResumeEditRead],
    status_code=status.HTTP_200_OK,
    summary="List proposed edits for an owned analysis",
)
async def list_resume_edits(
    analysis_id: UUID,
    service: Annotated[EditService, Depends(get_edit_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> list[ResumeEditRead]:
    try:
        return await service.list_edits(
            user_id=current_user_id,
            analysis_id=analysis_id,
        )
    except DomainError as exc:
        raise domain_error_to_http_exception(exc) from exc
    except Exception as exc:
        logger.exception("Listing resume edits failed")
        raise internal_error_to_http_exception() from exc


@router.post(
    "/analyses/{analysis_id}/edits/{edit_id}/reject",
    response_model=ResumeEditRead,
    status_code=status.HTTP_200_OK,
    summary="Reject a pending edit suggestion",
)
async def reject_resume_edit(
    analysis_id: UUID,
    edit_id: UUID,
    service: Annotated[EditService, Depends(get_edit_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> ResumeEditRead:
    try:
        return await service.reject_edit(
            user_id=current_user_id,
            analysis_id=analysis_id,
            edit_id=edit_id,
        )
    except DomainError as exc:
        raise domain_error_to_http_exception(exc) from exc
    except Exception as exc:
        logger.exception("Rejecting resume edit failed")
        raise internal_error_to_http_exception() from exc


@router.post(
    "/analyses/{analysis_id}/edits/{edit_id}/accept",
    response_model=ResumeVersionRead,
    status_code=status.HTTP_200_OK,
    summary="Accept a supported rewrite and re-score the working copy",
)
async def accept_resume_edit(
    analysis_id: UUID,
    edit_id: UUID,
    service: Annotated[EditService, Depends(get_edit_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> ResumeVersionRead:
    try:
        return await service.accept_edit(
            user_id=current_user_id,
            analysis_id=analysis_id,
            edit_id=edit_id,
        )
    except DomainError as exc:
        raise domain_error_to_http_exception(exc) from exc
    except Exception as exc:
        logger.exception("Accepting resume edit failed")
        raise internal_error_to_http_exception() from exc


@router.post(
    "/analyses/{analysis_id}/restore-original",
    response_model=ResumeVersionRead,
    status_code=status.HTTP_200_OK,
    summary="Create a new version from the immutable original resume",
)
async def restore_original_resume(
    analysis_id: UUID,
    service: Annotated[EditService, Depends(get_edit_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> ResumeVersionRead:
    try:
        return await service.restore_original(
            user_id=current_user_id,
            analysis_id=analysis_id,
        )
    except DomainError as exc:
        raise domain_error_to_http_exception(exc) from exc
    except Exception as exc:
        logger.exception("Restoring original resume failed")
        raise internal_error_to_http_exception() from exc


@router.post(
    "/analyses/{analysis_id}/versions/{version_id}/restore",
    response_model=ResumeVersionRead,
    status_code=status.HTTP_200_OK,
    summary="Create a new version that copies an earlier snapshot",
)
async def restore_resume_version(
    analysis_id: UUID,
    version_id: UUID,
    service: Annotated[EditService, Depends(get_edit_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> ResumeVersionRead:
    try:
        return await service.restore_version(
            user_id=current_user_id,
            analysis_id=analysis_id,
            version_id=version_id,
        )
    except DomainError as exc:
        raise domain_error_to_http_exception(exc) from exc
    except Exception as exc:
        logger.exception("Restoring resume version failed")
        raise internal_error_to_http_exception() from exc


@router.get(
    "/analyses/{analysis_id}/versions",
    response_model=list[ResumeVersionSummary],
    status_code=status.HTTP_200_OK,
    summary="List accepted resume versions",
)
async def list_resume_versions(
    analysis_id: UUID,
    service: Annotated[EditService, Depends(get_edit_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> list[ResumeVersionSummary]:
    try:
        return await service.list_versions(
            user_id=current_user_id,
            analysis_id=analysis_id,
        )
    except DomainError as exc:
        raise domain_error_to_http_exception(exc) from exc
    except Exception as exc:
        logger.exception("Listing resume versions failed")
        raise internal_error_to_http_exception() from exc


@router.get(
    "/analyses/{analysis_id}/versions/{version_id}",
    response_model=ResumeVersionRead,
    status_code=status.HTTP_200_OK,
    summary="Read one owned resume version",
)
async def get_resume_version(
    analysis_id: UUID,
    version_id: UUID,
    service: Annotated[EditService, Depends(get_edit_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> ResumeVersionRead:
    try:
        return await service.get_version(
            user_id=current_user_id,
            analysis_id=analysis_id,
            version_id=version_id,
        )
    except DomainError as exc:
        raise domain_error_to_http_exception(exc) from exc
    except Exception as exc:
        logger.exception("Reading resume version failed")
        raise internal_error_to_http_exception() from exc
