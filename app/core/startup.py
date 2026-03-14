from __future__ import annotations

import logging

from sqlalchemy import text

from app.core.database import async_session_factory, engine
from app.models.base import Base

logger = logging.getLogger(__name__)


def _import_models() -> None:
    """Import all ORM models so metadata is populated before create_all."""
    import app.models.resume_analysis  # noqa: F401
    import app.models.user  # noqa: F401
    import app.models.user_profile  # noqa: F401


async def initialize_database() -> None:
    """Create database tables if they do not already exist."""
    _import_models()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database schema initialized")


async def verify_database_connection() -> bool:
    """Return True when the database accepts connections."""
    async with async_session_factory() as session:
        await session.execute(text("SELECT 1"))
    return True
