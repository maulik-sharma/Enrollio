"""Segment filter validation and evaluation (M3.5).

The segment editor stores a JSONB filter definition. Evaluation converts it
into a SQLAlchemy ``select(Lead)`` with **only** whitelisted fields and
operators, so no user-controlled string can inject a column name, operator,
or raw SQL. Unknown fields/operators are domain errors, reported by the API
as 400s, and never reach the database.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, cast

from sqlalchemy import ColumnElement, Select, and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.campus import Campus
from app.models.lead import Lead
from app.models.lead_source import LeadSource
from app.models.programme import Programme
from app.models.segment import Segment
from app.models.student import Student

SAMPLE_LIMIT = 10

#: Field whitelist: segment JSON name → mapped column. Catalogue columns are
#: joined automatically when a condition references them; nothing outside
#: this table can appear in generated SQL.
FIELD_COLUMNS: dict[str, Any] = {
    # Lead columns (no join needed).
    "lifecycle_status": Lead.lifecycle_status,
    "admission_cycle": Lead.admission_cycle,
    "created_at": Lead.created_at,
    # Student columns (always joined).
    "first_name": Student.first_name,
    "last_name": Student.last_name,
    "email": Student.email_normalised,
    # Catalogue columns (joined on demand).
    "programme_code": Programme.code,
    "programme_name": Programme.name,
    "campus_name": Campus.name,
    "source_name": LeadSource.name,
}

NULL_OPS = frozenset({"is_null", "is_not_null"})
TEXT_OPS = frozenset({"contains", "starts_with"})
RANGE_OPS = frozenset({"gt", "gte", "lt", "lte"})
LIST_OPS = frozenset({"in", "not_in"})
SUPPORTED_OPS = (
    {
        "eq",
        "neq",
    }
    | NULL_OPS
    | TEXT_OPS
    | RANGE_OPS
    | LIST_OPS
)


class SegmentFilterError(Exception):
    """The filter definition is invalid and must be reported to the user."""

    def __init__(self, message: str, *, field_name: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.field_name = field_name


def validate_definition(definition: dict[str, Any]) -> None:
    """Validate the shape without touching SQL; raises ``SegmentFilterError``."""
    conditions = _conditions(definition)
    for condition in conditions:
        field_name = condition.get("field")
        if not isinstance(field_name, str) or field_name not in FIELD_COLUMNS:
            raise SegmentFilterError(
                f"field {field_name!r} is not filterable", field_name=_str(field_name)
            )
        op = condition.get("op")
        if not isinstance(op, str) or op not in SUPPORTED_OPS:
            raise SegmentFilterError(
                f"operator {op!r} is not supported for field {field_name!r}",
                field_name=field_name,
            )
        if op in NULL_OPS:
            continue
        if "value" not in condition:
            raise SegmentFilterError(f"operator {op!r} requires a value", field_name=field_name)
        if op in LIST_OPS and (
            not isinstance(condition["value"], list)
            or any(not isinstance(item, str) for item in condition["value"])
        ):
            raise SegmentFilterError(
                f"operator {op!r} requires a list of strings",
                field_name=field_name,
            )
        if field_name == "created_at" and op not in NULL_OPS:
            _parse_datetime(condition["value"], field_name)


def build_statement(definition: dict[str, Any]) -> Select[Any]:
    """Compile the definition into ``select(Lead)`` with whitelisted columns.

    Student is always joined (segments target people); catalogue tables join
    only when one of their fields is referenced. Returns a select whose
    leading column is the lead id ordered deterministically, ready for
    ``count`` and ``sample`` consumers.
    """
    validate_definition(definition)
    statement = (
        select(Lead)
        .options(
            selectinload(Lead.student),
            selectinload(Lead.programme),
            selectinload(Lead.campus),
            selectinload(Lead.assigned_counsellor),
        )
        .join(Student, Student.id == Lead.student_id)
        .order_by(Lead.created_at, Lead.id)
    )

    conditions = _conditions(definition)
    ordering_fields = {"programme_code", "programme_name", "campus_name", "source_name"}
    if ordering_fields & {condition.get("field") for condition in conditions}:
        statement = statement.join(Programme, Programme.id == Lead.programme_id, isouter=True)
        statement = statement.join(Campus, Campus.id == Lead.campus_id, isouter=True)
        statement = statement.join(LeadSource, LeadSource.id == Lead.source_id, isouter=True)

    predicates = [_predicate(condition) for condition in conditions]
    if predicates:
        statement = statement.where(and_(*predicates))
    return statement


async def count_matching(session: AsyncSession, definition: dict[str, Any]) -> int:
    """Number of leads matching the definition."""
    statement = build_statement(definition)
    rows = await session.scalars(statement)
    return len(list(rows))


async def sample_matching(
    session: AsyncSession,
    definition: dict[str, Any],
    *,
    limit: int = SAMPLE_LIMIT,
) -> list[Lead]:
    """First ``limit`` matching leads in stable order."""
    statement = build_statement(definition).limit(limit)
    rows = await session.scalars(statement)
    return list(rows)


def _predicate(condition: dict[str, Any]) -> ColumnElement[bool]:
    field_name = _str(condition["field"])
    column = _column(field_name)
    op = _str(condition["op"])
    raw_value = condition.get("value")

    if op == "is_null":
        return column.is_(None)
    if op == "is_not_null":
        return column.is_not(None)
    if op in TEXT_OPS:
        return column.ilike(_like_pattern(_str(raw_value), op), escape="\\")
    if op in RANGE_OPS:
        if field_name == "created_at":
            return _range_op(column, op, _parse_datetime(raw_value, field_name))
        return _range_op(column, op, _parse_number(raw_value, field_name))
    if op in LIST_OPS:
        values = [_str(item) for item in (raw_value if isinstance(raw_value, list) else [])]
        if op == "in":
            return column.in_(values)
        return column.not_in(values)
    if op == "eq":
        return _eq_op(column, _eq_value(field_name, raw_value))
    if op == "neq":
        return _neq_op(column, _eq_value(field_name, raw_value))
    raise SegmentFilterError(f"operator {op!r} is not supported", field_name=field_name)


def _column(field_name: str) -> ColumnElement[Any]:
    """The whitelisted column behind a field, or a validation error."""
    if field_name not in FIELD_COLUMNS:
        raise SegmentFilterError(f"field {field_name!r} is not filterable")
    return cast(ColumnElement[Any], FIELD_COLUMNS[field_name])


def _eq_op(column: ColumnElement[Any], value: Any) -> ColumnElement[bool]:
    return cast(ColumnElement[bool], column == value)


def _neq_op(column: ColumnElement[Any], value: Any) -> ColumnElement[bool]:
    return cast(ColumnElement[bool], column != value)


def _like_pattern(value: str, op: str) -> str:
    escaped = value.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%" if op == "contains" else f"{escaped}%"


def _range_op(column: ColumnElement[Any], op: str, value: Any) -> ColumnElement[bool]:
    if op == "gt":
        return cast(ColumnElement[bool], column > value)
    if op == "gte":
        return cast(ColumnElement[bool], column >= value)
    if op == "lt":
        return cast(ColumnElement[bool], column < value)
    if op == "lte":
        return cast(ColumnElement[bool], column <= value)
    raise SegmentFilterError(f"operator {op!r} is not supported")


def _eq_value(field_name: str, raw_value: Any) -> Any:
    if field_name == "created_at":
        return _parse_datetime(raw_value, field_name)
    return _str(raw_value)


def _parse_datetime(value: Any, field_name: str) -> datetime:
    try:
        return datetime.fromisoformat(_str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise SegmentFilterError(
            f"field {field_name!r} requires an ISO date-time value",
            field_name=field_name,
        ) from exc


def _parse_number(value: Any, field_name: str) -> float:
    try:
        return float(_str(value))
    except ValueError as exc:
        raise SegmentFilterError(
            f"field {field_name!r} requires a numeric value",
            field_name=field_name,
        ) from exc


def _conditions(definition: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(definition, dict):
        raise SegmentFilterError("filter definition must be a JSON object")
    conditions = definition.get("all")
    if conditions is None:
        raise SegmentFilterError("filter definition requires an 'all' list of conditions")
    if not isinstance(conditions, list):
        raise SegmentFilterError("'all' must be a list of conditions")
    for condition in conditions:
        if not isinstance(condition, dict):
            raise SegmentFilterError("each condition must be a JSON object")
    return conditions


def _str(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(_str(item) for item in value)
    return str(value)


async def save_segment(
    session: AsyncSession,
    *,
    name: str,
    filter_definition: dict[str, Any],
) -> Segment:
    """Validate the definition then persist the segment."""
    validate_definition(filter_definition)
    segment = Segment(name=name.strip(), filter_definition=filter_definition)
    session.add(segment)
    await session.flush()
    return segment


async def get_segment(session: AsyncSession, segment_id: uuid.UUID) -> Segment | None:
    return await session.scalar(select(Segment).where(Segment.id == segment_id))


__all__ = [
    "FIELD_COLUMNS",
    "SAMPLE_LIMIT",
    "SUPPORTED_OPS",
    "Segment",
    "SegmentFilterError",
    "build_statement",
    "count_matching",
    "get_segment",
    "sample_matching",
    "save_segment",
    "validate_definition",
]
