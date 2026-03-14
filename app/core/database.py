from __future__ import annotations

from collections.abc import AsyncGenerator
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


def _normalize_database_url(raw_url: str) -> tuple[str, dict[str, object]]:
    """
    Normalize DATABASE_URL for SQLAlchemy async engines.

    - PostgreSQL URLs are converted to the asyncpg driver.
    - sslmode=require is translated to asyncpg-compatible connect args.
    """
    connect_args: dict[str, object] = {}

    if raw_url.startswith("postgresql://"):
        async_url = raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif raw_url.startswith("postgres://"):
        async_url = raw_url.replace("postgres://", "postgresql+asyncpg://", 1)
    else:
        async_url = raw_url
        return async_url, connect_args

    parsed = urlparse(async_url)
    query = parse_qs(parsed.query)
    sslmode_values = query.get("sslmode", [])
    sslmode = sslmode_values[0] if sslmode_values else ""

    if sslmode in {"require", "verify-full", "verify-ca"}:
        connect_args["ssl"] = True

    if "sslmode" in query:
        del query["sslmode"]
        clean_query = urlencode({key: values[0] for key, values in query.items()})
        async_url = urlunparse(parsed._replace(query=clean_query))

    return async_url, connect_args


_async_url, _connect_args = _normalize_database_url(settings.DATABASE_URL)

engine = create_async_engine(
    _async_url,
    echo=False,
    pool_pre_ping=True,
    connect_args=_connect_args,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
