from __future__ import annotations

from collections.abc import AsyncGenerator
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


_ASYNCPG_IGNORED_QUERY_KEYS: frozenset[str] = frozenset({"sslmode", "channel_binding"})


def _first_query_value(query: dict[str, list[str]], key: str) -> str:
    values = query.get(key, [])
    return values[0] if values else ""


def _uses_connection_pooler(hostname: str, query: dict[str, list[str]]) -> bool:
    """Return True when the URL targets PgBouncer, including Neon pooler hosts."""
    host = hostname.lower()
    if "-pooler" in host or "pgbouncer" in host:
        return True
    return _first_query_value(query, "pgbouncer").lower() in {"1", "true", "yes"}


def _normalize_database_url(raw_url: str) -> tuple[str, dict[str, object]]:
    """
    Normalize DATABASE_URL for SQLAlchemy async engines.

    - PostgreSQL URLs are converted to the asyncpg driver.
    - sslmode / channel_binding are translated to asyncpg connect args.
    - PgBouncer and Neon pooler hosts disable the asyncpg statement cache.
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
    sslmode = _first_query_value(query, "sslmode")
    channel_binding = _first_query_value(query, "channel_binding")

    if sslmode in {"require", "verify-full", "verify-ca"} or channel_binding == "require":
        connect_args["ssl"] = True
    if _uses_connection_pooler(parsed.hostname or "", query):
        connect_args["statement_cache_size"] = 0

    for key in _ASYNCPG_IGNORED_QUERY_KEYS:
        query.pop(key, None)
    clean_query = urlencode({key: values[0] for key, values in query.items() if values})
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
