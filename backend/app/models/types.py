"""Reusable column types for domain enums."""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy import Enum


def enum_column(enum_type: type[StrEnum], name: str) -> Enum:
    """A VARCHAR column constrained to ``enum_type``'s values.

    ``native_enum`` is off so PostgreSQL does not own a type that has to be
    altered when the catalog grows; the check constraint is part of the table.
    """
    return Enum(
        enum_type,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda members: [member.value for member in members],
    )
