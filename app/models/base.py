from __future__ import annotations

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# JSONB on PostgreSQL, JSON elsewhere (SQLite local dev).
JsonColumn = JSON().with_variant(JSONB(), "postgresql")
