from __future__ import annotations

from fastapi import HTTPException, status

from app.core.errors import DomainError

def domain_error_to_http_exception(exc: DomainError) -> HTTPException:
    return HTTPException(
        status_code=exc.http_status,
        detail={"detail": exc.detail, "code": exc.code},
    )


def internal_error_to_http_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"detail": "Internal server error", "code": "internal_error"},
    )

