"""Unit tests for the segment whitelist, validation, and compiled SQL (M3.5).

The plan's security requirement: the evaluator converts filter JSON into SQL
using a whitelist. These tests compile the produced select with literal binds
and assert the exact predicates — proving no user string reaches SQL as
anything but a bound value.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.dialects import postgresql

from app.services.segments import (
    SAMPLE_LIMIT,
    SUPPORTED_OPS,
    SegmentFilterError,
    build_statement,
    validate_definition,
)


def compiled_sql(definition: dict[str, Any]) -> str:
    statement = build_statement(definition)
    return str(
        statement.compile(
            dialect=postgresql.dialect(),  # type: ignore[no-untyped-call]
            compile_kwargs={"literal_binds": True},
        ),
    )


def test_single_lifecycle_eq_predicate() -> None:
    sql = compiled_sql(
        {"all": [{"field": "lifecycle_status", "op": "eq", "value": "new_enquiry"}]},
    )
    assert "lifecycle_status = 'new_enquiry'" in sql


def test_admission_cycle_in_predicate() -> None:
    sql = compiled_sql(
        {"all": [{"field": "admission_cycle", "op": "in", "value": ["2026-fall", "2027-spring"]}]},
    )
    assert "admission_cycle IN ('2026-fall', '2027-spring')" in sql


def test_email_contains_escapes_wildcards() -> None:
    sql = compiled_sql(
        {"all": [{"field": "email", "op": "contains", "value": "as%ha_b"}]},
    )
    assert "email_normalised ILIKE '%%as\\%%ha\\_b%%'" in sql


def test_email_starts_with() -> None:
    sql = compiled_sql(
        {"all": [{"field": "email", "op": "starts_with", "value": "asha@"}]},
    )
    assert "ILIKE 'asha@%%'" in sql


def test_last_name_neq_predicate() -> None:
    sql = compiled_sql(
        {"all": [{"field": "last_name", "op": "neq", "value": "Rao"}]},
    )
    assert "last_name != 'Rao'" in sql


def test_created_at_range_uses_iso_value() -> None:
    sql = compiled_sql(
        {
            "all": [
                {
                    "field": "created_at",
                    "op": "gte",
                    "value": "2026-01-01T00:00:00+00:00",
                },
            ],
        },
    )
    assert "created_at >= '2026-01-01 00:00:00+00:00'" in sql


def test_catalogue_fields_are_outer_joined() -> None:
    sql = compiled_sql(
        {"all": [{"field": "campus_name", "op": "is_null"}]},
    )
    assert "name IS NULL" in sql
    assert "OUTER JOIN" in sql  # catalogue tables join without dropping NULL rows


def test_source_not_in_predicate_and_multiple_conditions_and_join() -> None:
    sql = compiled_sql(
        {
            "all": [
                {"field": "source_name", "op": "not_in", "value": ["Referral"]},
                {"field": "first_name", "op": "eq", "value": "Asha"},
            ],
        },
    )
    assert "name NOT IN ('Referral')" in sql
    assert "students.first_name = 'Asha'" in sql
    assert " AND " in sql  # multiple conditions conjunction


def test_is_not_null_created_at() -> None:
    sql = compiled_sql(
        {"all": [{"field": "source_name", "op": "is_not_null"}]},
    )
    assert "name IS NOT NULL" in sql


def test_contains_backslash_is_escaped() -> None:
    sql = compiled_sql(
        {"all": [{"field": "first_name", "op": "contains", "value": "a\\b"}]},
    )
    assert "ILIKE '%%a\\\\b%%'" in sql


def test_student_is_always_joined() -> None:
    sql = compiled_sql(
        {"all": [{"field": "lifecycle_status", "op": "is_not_null"}]},
    )
    assert "students" in sql


def test_unknown_field_is_rejected_before_sql() -> None:
    with pytest.raises(SegmentFilterError) as error:
        validate_definition(
            {"all": [{"field": "first_name; DROP TABLE leads", "op": "eq", "value": "x"}]},
        )
    assert "is not filterable" in error.value.message


def test_unknown_op_is_rejected() -> None:
    with pytest.raises(SegmentFilterError) as error:
        validate_definition({"all": [{"field": "first_name", "op": "raw_sql", "value": "x"}]})
    assert "operator 'raw_sql' is not supported" in error.value.message


def test_in_requires_a_list_of_strings() -> None:
    with pytest.raises(SegmentFilterError) as error:
        validate_definition({"all": [{"field": "admission_cycle", "op": "in", "value": "2026"}]})
    assert "list of strings" in error.value.message


def test_created_at_requires_iso_value() -> None:
    with pytest.raises(SegmentFilterError) as error:
        validate_definition(
            {"all": [{"field": "created_at", "op": "gte", "value": "next tuesday"}]},
        )
    assert "ISO" in error.value.message


def test_missing_value_is_rejected() -> None:
    with pytest.raises(SegmentFilterError) as error:
        validate_definition({"all": [{"field": "first_name", "op": "eq"}]})
    assert "requires a value" in error.value.message


def test_malformed_shapes_are_rejected() -> None:
    with pytest.raises(SegmentFilterError):
        validate_definition({})
    with pytest.raises(SegmentFilterError):
        validate_definition({"all": "first_name = x"})
    with pytest.raises(SegmentFilterError):
        validate_definition({"all": ["first_name = x"]})


def test_supported_ops_match_the_plan() -> None:
    assert {
        "eq",
        "neq",
        "in",
        "not_in",
        "contains",
        "starts_with",
        "gt",
        "gte",
        "lt",
        "lte",
        "is_null",
        "is_not_null",
    } == SUPPORTED_OPS


def test_sample_limit_default_is_capped() -> None:
    assert SAMPLE_LIMIT == 10


def test_created_at_predicate_accepts_a_datetime_object() -> None:
    # Validation accepts both strings and datetime objects (API sends strings;
    # service-level callers may pass datetimes directly).
    validate_definition(
        {
            "all": [
                {
                    "field": "created_at",
                    "op": "lt",
                    "value": datetime(2026, 1, 1, tzinfo=UTC),
                },
            ]
        },
    )
