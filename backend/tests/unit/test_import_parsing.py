"""Pure import parsing, mapping, and row-validation tests (M2.3)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from app.services.import_parsing import (
    ImportFileError,
    ImportMappingError,
    ImportRowError,
    parse_import_file,
    validate_import_row,
    validate_mapping,
)
from tests.fixtures.import_files import (
    HEADERS,
    MAPPER,
    clean_csv,
    clean_xlsx,
    merged_header_xlsx,
    too_many_rows_csv,
)

SIMPLE_ROW: dict[str, Any] = {
    "name": "Asha Rao",
    "email": "ASHA@Example.com",
    "phone": "9876543210",
    "course": "B.Tech Computer Science",
    "score": "85%",
    "graduation_year": "2027",
    "source": "Website",
    "campus": "Main Campus",
    "admission_cycle": "2026-fall",
}
SIMPLE_MAPPING = {field: field for field in SIMPLE_ROW}


def test_validate_import_row_normalises_all_fields() -> None:
    row = validate_import_row(SIMPLE_ROW, SIMPLE_MAPPING)

    assert row.first_name == "Asha"
    assert row.last_name == "Rao"
    assert row.email == "asha@example.com"
    assert row.phone == "+919876543210"
    assert row.programme == "B.Tech Computer Science"
    assert row.score == Decimal("85")
    assert row.graduation_year == 2027
    assert row.source == "Website"
    assert row.campus == "Main Campus"
    assert row.admission_cycle == "2026-fall"


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"email": "", "phone": ""}, "missing_contact"),
        ({"name": ""}, "invalid_name"),
        ({"email": "not-an-email"}, "invalid_email"),
        ({"email": "", "phone": "12345"}, "invalid_phone"),
        ({"score": "abc"}, "invalid_score"),
        ({"graduation_year": "next year"}, "invalid_graduation_year"),
        ({"graduation_year": "3000"}, "invalid_graduation_year"),
        ({"name": "A" * 101}, "invalid_name"),
        ({"course": "C" * 201}, "invalid_course"),
        ({"admission_cycle": "C" * 33}, "invalid_admission_cycle"),
    ],
)
def test_validate_import_row_rejects_with_stable_codes(
    overrides: dict[str, Any],
    code: str,
) -> None:
    with pytest.raises(ImportRowError) as exc_info:
        validate_import_row({**SIMPLE_ROW, **overrides}, SIMPLE_MAPPING)

    assert exc_info.value.code == code


def test_validate_import_row_email_only() -> None:
    row = validate_import_row({**SIMPLE_ROW, "phone": ""}, SIMPLE_MAPPING)
    assert row.email == "asha@example.com"
    assert row.phone is None


def test_validate_import_row_phone_only() -> None:
    row = validate_import_row({**SIMPLE_ROW, "email": ""}, SIMPLE_MAPPING)
    assert row.email is None
    assert row.phone == "+919876543210"


def test_validate_import_row_optional_fields_may_be_blank() -> None:
    row = validate_import_row(
        {
            **SIMPLE_ROW,
            "course": "",
            "score": "",
            "graduation_year": "",
            "source": "",
            "campus": "",
            "admission_cycle": "",
        },
        SIMPLE_MAPPING,
    )

    assert row.programme is None
    assert row.score is None
    assert row.graduation_year is None
    assert row.source is None
    assert row.campus is None
    assert row.admission_cycle == str(datetime.now(UTC).year)


def test_validate_import_row_splits_multipart_names() -> None:
    row = validate_import_row({**SIMPLE_ROW, "name": "Asha Rao Kulkarni"}, SIMPLE_MAPPING)
    assert row.first_name == "Asha"
    assert row.last_name == "Rao Kulkarni"


def test_validate_mapping_accepts_a_complete_mapping() -> None:
    assert validate_mapping(MAPPER, HEADERS) == MAPPER


@pytest.mark.parametrize(
    ("mapping", "message"),
    [
        ({"Missing": "name"}, "Unknown source column"),
        ({"Full Name": "nickname"}, "Unknown system field"),
        ({"Full Name": "name", "Email": "name"}, "mapped more than once"),
        ({"Email": "email"}, "Required fields are not mapped"),
        ({}, "At least one column"),
    ],
)
def test_validate_mapping_rejects_bad_mappings(
    mapping: dict[str, str],
    message: str,
) -> None:
    with pytest.raises(ImportMappingError, match=message):
        validate_mapping(mapping, HEADERS)


def test_parse_csv_detects_headers_and_preserves_row_numbers() -> None:
    parsed = parse_import_file(
        "clean.csv",
        clean_csv(count=2),
        max_rows=10,
        max_bytes=1_000_000,
    )

    assert parsed.headers == HEADERS
    assert parsed.file_type == "csv"
    assert [number for number, _ in parsed.rows] == [2, 3]
    assert parsed.rows[0][1]["Full Name"] == "Student 1"


def test_parse_csv_skips_blank_rows() -> None:
    content = b"Full Name,Email\nAsha,asha@example.com\n,\nRavi,ravi@example.com\n"
    parsed = parse_import_file("rows.csv", content, max_rows=10, max_bytes=1_000_000)

    assert [number for number, _ in parsed.rows] == [2, 4]


@pytest.mark.parametrize(
    ("content", "code"),
    [
        (b"", "empty_file"),
        (b"Full Name\n", "empty_file"),
        (b"Full Name,full name\nAsha,Asha\n", "duplicate_headers"),
        (b"Full Name,\nAsha,Rao\n", "empty_headers"),
        (b"Full Name,Email\nAsha,asha@example.com,extra\n", "invalid_csv"),
    ],
)
def test_parse_csv_rejects_malformed_files(content: bytes, code: str) -> None:
    with pytest.raises(ImportFileError) as exc_info:
        parse_import_file("bad.csv", content, max_rows=10, max_bytes=1_000_000)

    assert exc_info.value.code == code


def test_parse_rejects_unsupported_extension() -> None:
    with pytest.raises(ImportFileError) as exc_info:
        parse_import_file("leads.txt", b"a,b\n1,2\n", max_rows=10, max_bytes=1_000_000)

    assert exc_info.value.code == "unsupported_file_type"
    assert exc_info.value.status_code == 415


def test_parse_rejects_file_larger_than_limit() -> None:
    with pytest.raises(ImportFileError) as exc_info:
        parse_import_file("large.csv", b"a" * 20, max_rows=10, max_bytes=10)

    assert exc_info.value.code == "file_too_large"
    assert exc_info.value.status_code == 413


def test_parse_rejects_more_rows_than_limit() -> None:
    with pytest.raises(ImportFileError) as exc_info:
        parse_import_file(
            "many.csv",
            too_many_rows_csv(max_rows=3),
            max_rows=3,
            max_bytes=1_000_000,
        )

    assert exc_info.value.code == "too_many_rows"
    assert exc_info.value.status_code == 413


def test_parse_xlsx_reads_the_active_sheet() -> None:
    parsed = parse_import_file("clean.xlsx", clean_xlsx(), max_rows=10, max_bytes=1_000_000)

    assert parsed.headers == HEADERS
    assert parsed.file_type == "xlsx"
    assert parsed.rows[0][0] == 2
    assert parsed.rows[0][1]["Full Name"] == "Student 1"


def test_parse_xlsx_rejects_merged_header_cells() -> None:
    with pytest.raises(ImportFileError) as exc_info:
        parse_import_file(
            "merged.xlsx",
            merged_header_xlsx(),
            max_rows=10,
            max_bytes=1_000_000,
        )

    assert exc_info.value.code == "merged_headers"
    assert "Merged cells" in str(exc_info.value)
