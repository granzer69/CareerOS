from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import DomainError, domain_error_to_http_exception, internal_error_to_http_exception
from app.core.auth import get_current_user_id
from app.core.database import get_db_session
from app.schemas.user_profile import (
    UserProfileCreate,
    UserProfileRead,
    UserProfileUpdate,
)
from app.services.user_profile_service import UserProfileService


router = APIRouter(prefix="/user-profile", tags=["user-profile"])


async def get_user_profile_service(
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserProfileService:
    return UserProfileService(db_session=db_session)


@router.post(
    "/{user_id}",
    response_model=UserProfileRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_user_profile(
    user_id: UUID,
    payload: UserProfileCreate,
    service: Annotated[UserProfileService, Depends(get_user_profile_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> UserProfileRead:
    try:
        return await service.upsert_user_profile(
            current_user_id=current_user_id,
            user_id=user_id,
            payload=payload,
        )
    except DomainError as exc:
        raise domain_error_to_http_exception(exc) from exc
    except Exception as exc:
        raise internal_error_to_http_exception() from exc


@router.put(
    "/{user_id}",
    response_model=UserProfileRead,
    status_code=status.HTTP_200_OK,
)
async def update_user_profile(
    user_id: UUID,
    payload: UserProfileUpdate,
    service: Annotated[UserProfileService, Depends(get_user_profile_service)],
    current_user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> UserProfileRead:
    try:
        return await service.upsert_user_profile(
            current_user_id=current_user_id,
            user_id=user_id,
            payload=payload,
        )
    except DomainError as exc:
        raise domain_error_to_http_exception(exc) from exc
    except Exception as exc:
        raise internal_error_to_http_exception() from exc

