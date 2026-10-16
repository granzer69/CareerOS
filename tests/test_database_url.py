from __future__ import annotations

from app.core.database import _normalize_database_url


def test_neon_pooler_url_disables_statement_cache_and_drops_libpq_params() -> None:
    """Neon pooler URLs must be valid asyncpg URLs and must not cache statements."""
    async_url, connect_args = _normalize_database_url(
        "postgresql://user:secret@ep-example-pooler.c-2.us-east-2.aws.neon.tech/neondb"
        "?sslmode=require&channel_binding=require"
    )

    assert async_url.startswith("postgresql+asyncpg://")
    assert "sslmode" not in async_url
    assert "channel_binding" not in async_url
    assert "secret" in async_url
    assert connect_args["ssl"] is True
    assert connect_args["statement_cache_size"] == 0


def test_direct_postgres_url_keeps_default_statement_cache() -> None:
    """A direct Postgres URL does not force the PgBouncer statement-cache workaround."""
    async_url, connect_args = _normalize_database_url(
        "postgresql://user:secret@localhost:5432/careeros"
    )

    assert async_url == "postgresql+asyncpg://user:secret@localhost:5432/careeros"
    assert connect_args == {}
