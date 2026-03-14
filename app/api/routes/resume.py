from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import DomainError, domain_error_to_http_exception, internal_error_to_http_exception
from app.core.database import get_db_session
from app.schemas.resume_analysis import ResumeAnalysisRead
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
        "Upload a PDF or DOCX resume (max 5 MB) along with a target role. "
        "The system extracts the text, sends it to Claude for analysis, and "
        "returns a structured score with detailed section-level feedback."
    ),
)
async def analyze_resume(
    file: UploadFile,
    target_role: Annotated[str, Form(min_length=1, max_length=200)],
    service: Annotated[ResumeService, Depends(get_resume_service)],
) -> ResumeAnalysisRead:
    try:
        file_bytes = await file.read()
        return await service.analyze_resume(
            file_bytes=file_bytes,
            file_name=file.filename or "unknown",
            content_type=file.content_type or "",
            target_role=target_role,
        )
    except DomainError as exc:
        raise domain_error_to_http_exception(exc) from exc
    except Exception as exc:
        logger.exception("Resume analysis failed")
        raise internal_error_to_http_exception() from exc
