"""Lead source model: where an enquiry came from."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.lead import Lead


class LeadSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A named acquisition channel, e.g. website form or education fair."""

    __tablename__ = "lead_sources"

    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False, server_default="")

    leads: Mapped[list[Lead]] = relationship(back_populates="source")
