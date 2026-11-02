"""Programme model: the course a lead enquires about."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.lead import Lead


class Programme(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An academic programme, optionally identified by a short code."""

    __tablename__ = "programmes"

    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    code: Mapped[str | None] = mapped_column(String(32), nullable=True, unique=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )

    leads: Mapped[list[Lead]] = relationship(back_populates="programme")
