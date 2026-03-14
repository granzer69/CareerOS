from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DomainError(Exception):
    detail: str
    code: str
    http_status: int

