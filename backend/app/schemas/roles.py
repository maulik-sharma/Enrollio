"""Role administration request and response schemas."""

from __future__ import annotations

import uuid

from pydantic import BaseModel


class RoleRead(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    description: str
    permissions: list[str]


class RolePermissionsUpdate(BaseModel):
    permissions: list[str]
