"""SQLAlchemy models. Importing this package registers every table on Base."""

from __future__ import annotations

from app.models.base import Base
from app.models.permission import Permission
from app.models.refresh_token import RefreshToken
from app.models.role import Role
from app.models.user import User

__all__ = ["Base", "Permission", "RefreshToken", "Role", "User"]
