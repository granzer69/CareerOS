from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.core.database import async_session_factory, engine
from app.models.base import Base

logger = logging.getLogger(__name__)


def _import_models() -> None:
    """Import all ORM models so metadata is populated before create_all."""
    import app.models.resume_analysis  # noqa: F401
    import app.models.resume_edit  # noqa: F401
    import app.models.user  # noqa: F401
    import app.models.user_profile  # noqa: F401


async def _verify_required_columns() -> None:
    """Fail closed when create_all left a leftover sqlite schema without later columns."""
    async with async_session_factory() as session:
        try:
            await session.execute(text("SELECT user_id FROM resume_analyses WHERE 1=0"))
        except (OperationalError, ProgrammingError) as exc:
            raise RuntimeError(
                "Database schema is behind Alembic (missing resume_analyses.user_id). "
                "Delete leftover local sqlite and run `alembic upgrade head`. "
                "create_all does not add columns to existing tables."
            ) from exc


async def initialize_database() -> None:
    """Create database tables if they do not already exist, then check required columns."""
    _import_models()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _verify_required_columns()
    logger.info("Database schema initialized")


async def verify_database_connection() -> bool:
    """Return True when the database accepts connections."""
    async with async_session_factory() as session:
        await session.execute(text("SELECT 1"))
    return True
