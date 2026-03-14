from __future__ import annotations

from datetime import datetime
from typing import List
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import ExperienceLevelEnum


class UserProfileBase(BaseModel):
    user_id: UUID = Field(...)
    skills: List[str] = Field(default_factory=list)
    target_role: str = Field(...)
    experience_level: ExperienceLevelEnum = Field(...)

    model_config = {
        "validate_assignment": True,
        "extra": "forbid",
    }


class UserProfileCreate(UserProfileBase):
    pass


class UserProfileUpdate(BaseModel):
    skills: List[str] | None = None
    target_role: str | None = None
    experience_level: ExperienceLevelEnum | None = None

    model_config = {
        "validate_assignment": True,
        "extra": "forbid",
    }


class UserProfileRead(UserProfileBase):
    id: UUID
    created_at: datetime

    model_config = {
        "from_attributes": True,
        "validate_assignment": True,
        "extra": "forbid",
    }

