"""Association tables for identity and RBAC."""

from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Table, Uuid

from app.models.base import Base

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column(
        "user_id",
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "role_id",
        Uuid,
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    ),
)

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column(
        "role_id",
        Uuid,
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "permission_id",
        Uuid,
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    ),
)
