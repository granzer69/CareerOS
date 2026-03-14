"""Initialize database tables for CareerOS."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.startup import initialize_database


async def main() -> None:
    await initialize_database()
    print("Database tables are ready.")


if __name__ == "__main__":
    asyncio.run(main())
