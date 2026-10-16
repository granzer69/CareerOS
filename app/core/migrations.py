from __future__ import annotations

import asyncio
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from app.core.config import settings

logger = logging.getLogger(__name__)

_URL_RE = re.compile(r"postgres(?:ql)?(?:\+\w+)?://\S+")
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _redact_urls(text: str) -> str:
    """Remove database URLs from command output before it is logged."""
    return _URL_RE.sub("postgresql://redacted", text)


def direct_database_url(raw_url: str) -> str:
    """Return a non-pooled URL so Alembic locks are not sent through PgBouncer."""
    parsed = urlparse(raw_url)
    hostname = parsed.hostname or ""
    if "-pooler" not in hostname:
        return raw_url
    direct_host = hostname.replace("-pooler", "", 1)
    netloc = parsed.netloc.replace(hostname, direct_host, 1)
    return urlunparse(parsed._replace(netloc=netloc))


def upgrade_database() -> None:
    """Apply Alembic migrations to the configured database."""
    env = os.environ.copy()
    configured_url = env.get("DATABASE_URL", "")
    if configured_url:
        env["DATABASE_URL"] = direct_database_url(configured_url)
    completed = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=_REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    if completed.returncode != 0:
        detail = _redact_urls(completed.stderr or completed.stdout or "").strip()
        logger.error(
            "Alembic upgrade failed with exit code %s: %s",
            completed.returncode,
            detail[-2000:],
        )
        raise RuntimeError("Alembic upgrade failed")
    logger.info("Alembic upgrade head completed")


async def apply_startup_migrations() -> None:
    """Run Alembic when RUN_MIGRATIONS is enabled. Render uses its pre-deploy command instead."""
    if not settings.RUN_MIGRATIONS:
        return
    await asyncio.to_thread(upgrade_database)
