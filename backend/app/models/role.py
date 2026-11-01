"""Role model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.associations import role_permissions, user_roles
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.permission import Permission
    from app.models.user import User


class Role(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A named bundle of permissions, e.g. Admission Manager."""

    __tablename__ = "roles"

    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False, server_default="")

    users: Mapped[list[User]] = relationship(
        secondary=user_roles,
        back_populates="roles",
    )
    permissions: Mapped[list[Permission]] = relationship(
        secondary=role_permissions,
        back_populates="roles",
        lazy="selectin",
    )
