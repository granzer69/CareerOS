from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.core.database import async_session_factory
from app.core.errors import DomainError
from app.schemas.analysis_job import AnalysisJobRead
from app.schemas.resume_analysis import ResumeAnalysisRead
from app.services.resume_service import ResumeService

logger = logging.getLogger(__name__)

_TERMINAL = frozenset({"completed", "failed"})


@dataclass
class _JobRecord:
    id: UUID
    user_id: UUID
    status: str
    created_at: datetime
    updated_at: datetime
    analysis: ResumeAnalysisRead | None = None
    error_code: str | None = None
    error_detail: str | None = None
    task: asyncio.Task[None] | None = field(default=None, repr=False)


_jobs: dict[UUID, _JobRecord] = {}
_jobs_lock = asyncio.Lock()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_read(record: _JobRecord) -> AnalysisJobRead:
    return AnalysisJobRead(
        id=record.id,
        status=record.status,
        created_at=record.created_at,
        updated_at=record.updated_at,
        analysis=record.analysis,
        error_code=record.error_code,
        error_detail=record.error_detail,
    )


async def create_analysis_job(
    *,
    user_id: UUID,
    file_bytes: bytes,
    file_name: str,
    content_type: str,
    target_role: str,
    job_description: str,
) -> AnalysisJobRead:
    """
    Queue resume analysis on a background task and return immediately.

    Avoids long-lived HTTP requests that reverse proxies (e.g. Cloudflare tunnels)
    may terminate before local GGUF inference finishes.
    """
    job_id = uuid4()
    now = _utc_now()
    record = _JobRecord(
        id=job_id,
        user_id=user_id,
        status="pending",
        created_at=now,
        updated_at=now,
    )
    async with _jobs_lock:
        _jobs[job_id] = record

    record.task = asyncio.create_task(
        _run_job(
            job_id=job_id,
            user_id=user_id,
            file_bytes=file_bytes,
            file_name=file_name,
            content_type=content_type,
            target_role=target_role,
            job_description=job_description,
        ),
        name=f"analysis-job-{job_id}",
    )
    return _to_read(record)


async def get_analysis_job(*, job_id: UUID, user_id: UUID) -> AnalysisJobRead:
    """Return one job for the authenticated owner."""
    async with _jobs_lock:
        record = _jobs.get(job_id)
    if record is None or record.user_id != user_id:
        raise AnalysisJobNotFoundError()
    return _to_read(record)


class AnalysisJobNotFoundError(Exception):
    """Raised when a job id is unknown or owned by another user."""


def _run_job_blocking(
    *,
    job_id: UUID,
    user_id: UUID,
    file_bytes: bytes,
    file_name: str,
    content_type: str,
    target_role: str,
    job_description: str,
) -> tuple[str, ResumeAnalysisRead | None, str | None, str | None]:
    """
    Blocking worker entrypoint. Returns (terminal_status, analysis, error_code, error_detail).
    """
    async def _execute() -> ResumeAnalysisRead:
        async with async_session_factory() as session:
            service = ResumeService(db_session=session)
            return await service.analyze_resume(
                file_bytes=file_bytes,
                file_name=file_name,
                content_type=content_type,
                target_role=target_role,
                job_description=job_description,
                user_id=user_id,
            )

    try:
        analysis = asyncio.run(_execute())
        return ("completed", analysis, None, None)
    except DomainError as exc:
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return ("failed", None, exc.code, detail)
    except Exception:
        logger.exception("Background analysis job %s failed", job_id)
        return ("failed", None, "analysis_failed", "Resume analysis failed")


async def _run_job(
    *,
    job_id: UUID,
    user_id: UUID,
    file_bytes: bytes,
    file_name: str,
    content_type: str,
    target_role: str,
    job_description: str,
) -> None:
    async with _jobs_lock:
        record = _jobs.get(job_id)
        if record is None:
            return
        record.status = "running"
        record.updated_at = _utc_now()

    status, analysis, error_code, error_detail = await asyncio.to_thread(
        _run_job_blocking,
        job_id=job_id,
        user_id=user_id,
        file_bytes=file_bytes,
        file_name=file_name,
        content_type=content_type,
        target_role=target_role,
        job_description=job_description,
    )

    async with _jobs_lock:
        record = _jobs.get(job_id)
        if record is None:
            return
        record.status = status
        record.analysis = analysis
        record.error_code = error_code
        record.error_detail = error_detail
        record.updated_at = _utc_now()
