"""Authentication request and response schemas."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class RoleSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str


class CurrentUser(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    roles: list[RoleSummary]
    permissions: list[str]


class StatusResponse(BaseModel):
    status: Literal["ok"] = "ok"
