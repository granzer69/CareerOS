from __future__ import annotations

import asyncio
import logging
import subprocess

import pytest

from app.core.config import settings
from app.core.migrations import apply_startup_migrations, direct_database_url, upgrade_database


def test_direct_database_url_strips_neon_pooler_host() -> None:
    """Migrations use the direct Neon host so PgBouncer does not drop session locks."""
    raw = "postgresql://user:secret@ep-example-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require"
    direct = direct_database_url(raw)
    assert "-pooler" not in direct
    assert "ep-example.c-2.us-east-2.aws.neon.tech" in direct
    assert "secret" in direct
    assert direct_database_url("postgresql://user:secret@localhost/careeros").endswith("@localhost/careeros")


def test_startup_migrations_skip_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Render keeps using its pre-deploy command, so startup stays a no-op by default."""
    monkeypatch.setattr(settings, "RUN_MIGRATIONS", False)
    called = False

    def _fail_if_called() -> None:
        nonlocal called
        called = True
        raise AssertionError("upgrade_database should not run")

    monkeypatch.setattr("app.core.migrations.upgrade_database", _fail_if_called)
    asyncio.run(apply_startup_migrations())
    assert called is False


def test_upgrade_database_raises_without_leaking_the_url(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A failed Alembic run surfaces a generic error and redacts the database URL."""

    def _failed_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["alembic"],
            returncode=1,
            stdout="",
            stderr="failed postgresql://user:secret@db.example/careeros",
        )

    monkeypatch.setattr("app.core.migrations.subprocess.run", _failed_run)
    with caplog.at_level(logging.ERROR):
        with pytest.raises(RuntimeError, match="Alembic upgrade failed"):
            upgrade_database()
    assert "secret" not in caplog.text
    assert "postgresql://redacted" in caplog.text
