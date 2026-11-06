"""Reusable segments: named JSONB filters over leads."""

from __future__ import annotations

from typing import Any

from sqlalchemy import String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Segment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A named, shareable filter definition evaluated at launch time (FR-09).

    The JSONB shape is ``{"all": [{"field": ..., "op": ..., "value": ...},
    ...]}`` and is validated against a whitelist of filterable fields before
    the evaluator touches SQL, so foreign or malicious fields never reach a
    query. Segments snapshot nothing: a campaign's recipients are recorded at
    launch.
    """

    __tablename__ = "segments"

    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    filter_definition: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
