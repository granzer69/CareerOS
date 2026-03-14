from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that yields an AsyncSession.

    NOTE: The actual engine/sessionmaker wiring should be added in app/core/config.py
    and app/core/database initialization when the project scaffolding is completed.
    """
    raise NotImplementedError("Database session wiring not yet configured")

