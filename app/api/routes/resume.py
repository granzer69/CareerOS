from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import DomainError, domain_error_to_http_exception, internal_error_to_http_exception
from app.core.auth import get_current_user_id
from app.core.database import get_db_session
from app.schemas.resume_analysis import ResumeAnalysisRead, ResumeAnalysisSummary
from app.services.resume_service import ResumeService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/resume", tags=["resume"])


async def get_resume_service(
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ResumeService:
    return ResumeService(db_session=db_session)


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
