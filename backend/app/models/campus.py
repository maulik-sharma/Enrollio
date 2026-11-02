"""Campus model: a physical location where a programme is offered."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.lead import Lead


class Campus(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A campus or study location."""

    __tablename__ = "campuses"

    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )

    leads: Mapped[list[Lead]] = relationship(back_populates="campus")
