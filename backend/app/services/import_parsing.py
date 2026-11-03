"""Pure parsing and row validation for CSV/XLSX lead imports."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal, InvalidOperation
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from app.core.normalisation import (
    InvalidEmail,
    InvalidName,
    InvalidPhone,
    InvalidScore,
    normalise_email,
    normalise_name,
    normalise_phone,
    normalise_score,
)

SYSTEM_FIELDS = frozenset(
    {
        "name",
        "email",
        "phone",
        "course",
        "score",
        "graduation_year",
        "source",
        "campus",
        "admission_cycle",
    }
)
REQUIRED_MAPPING_FIELDS = frozenset({"name"})

CSV_EXTENSIONS = frozenset({".csv"})
XLSX_EXTENSIONS = frozenset({".xlsx"})


class ImportFileError(ValueError):
    """An uploaded file cannot be parsed."""

    def __init__(self, code: str, message: str, *, status_code: int = 422) -> None:
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class ImportMappingError(ValueError):
    """A column mapping is incomplete or invalid."""

    code = "invalid_mapping"


class ImportRowError(ValueError):
    """One row is invalid; ``code`` is stored as the rejection reason."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class ParsedImport:
    """Headers and non-empty data rows with their original 1-based row numbers."""

    headers: list[str]
    rows: list[tuple[int, dict[str, Any]]]
    file_type: str


@dataclass(frozen=True)
class ValidatedImportRow:
    """A row after normalisation, before catalogue lookups and persistence."""

    first_name: str
    last_name: str
    email: str | None
    phone: str | None
    programme: str | None
    score: Decimal | None
    graduation_year: int | None
    source: str | None
    campus: str | None
    admission_cycle: str


def parse_import_file(
    filename: str,
    data: bytes,
    *,
    max_rows: int,
    max_bytes: int,
) -> ParsedImport:
    """Parse an uploaded CSV/XLSX file, rejecting malformed or oversized input."""
    if not data:
        raise ImportFileError("empty_file", "The uploaded file is empty")

    if len(data) > max_bytes:
        raise ImportFileError(
            "file_too_large",
            f"File exceeds the {max_bytes} byte limit",
            status_code=413,
        )

    extension = Path(filename).suffix.lower()
    if extension in CSV_EXTENSIONS:
        parsed = _parse_csv(data)
    elif extension in XLSX_EXTENSIONS:
        parsed = _parse_xlsx(data)
    else:
        raise ImportFileError(
            "unsupported_file_type",
            "Only .csv and .xlsx files are supported",
            status_code=415,
        )

    if len(parsed.rows) > max_rows:
        raise ImportFileError(
            "too_many_rows",
            f"File has {len(parsed.rows)} rows; the limit is {max_rows}",
            status_code=413,
        )

    return parsed


def validate_mapping(mapping: dict[str, str], headers: list[str]) -> dict[str, str]:
    """Check that a source-column mapping is complete and unambiguous."""
    if not mapping:
        raise ImportMappingError("At least one column must be mapped")

    available = set(headers)
    mapped_fields: set[str] = set()
    cleaned: dict[str, str] = {}

    for source, system in mapping.items():
        if source not in available:
            raise ImportMappingError(f"Unknown source column: {source}")
        if system not in SYSTEM_FIELDS:
            raise ImportMappingError(f"Unknown system field: {system}")
        if system in mapped_fields:
            raise ImportMappingError(f"System field mapped more than once: {system}")
        mapped_fields.add(system)
        cleaned[source] = system

    missing = REQUIRED_MAPPING_FIELDS - mapped_fields
    if missing:
        raise ImportMappingError(f"Required fields are not mapped: {', '.join(sorted(missing))}")

    return cleaned


def validate_import_row(row: dict[str, Any], mapping: dict[str, str]) -> ValidatedImportRow:
    """Normalise one mapped row or raise ``ImportRowError`` with a stable code."""
    mapped = {system: row.get(source) for source, system in mapping.items()}

    try:
        name = normalise_name(_text(mapped.get("name")))
    except InvalidName as exc:
        raise ImportRowError(exc.code, str(exc)) from exc

    name_parts = name.split(maxsplit=1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else ""
    if len(first_name) > 100 or len(last_name) > 100:
        raise ImportRowError("invalid_name", "Name parts are longer than 100 characters")

    email = _normalise_optional_email(mapped.get("email"))
    phone = _normalise_optional_phone(mapped.get("phone"))
    if email is None and phone is None:
        raise ImportRowError("missing_contact", "A row needs an email or a phone number")

    score = _normalise_optional_score(mapped.get("score"))
    graduation_year = _normalise_optional_year(mapped.get("graduation_year"))

    return ValidatedImportRow(
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
        programme=_catalogue_value(mapped.get("course"), field="course", max_length=200),
        score=score,
        graduation_year=graduation_year,
        source=_catalogue_value(mapped.get("source"), field="source", max_length=100),
        campus=_catalogue_value(mapped.get("campus"), field="campus", max_length=200),
        admission_cycle=_admission_cycle(mapped.get("admission_cycle")),
    )


def _parse_csv(data: bytes) -> ParsedImport:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ImportFileError("invalid_encoding", "CSV files must be UTF-8 encoded") from exc

    reader = csv.reader(StringIO(text))
    try:
        header_row = next(reader)
    except StopIteration as exc:
        raise ImportFileError("empty_file", "The uploaded file is empty") from exc

    headers = _clean_headers(header_row)
    rows: list[tuple[int, dict[str, Any]]] = []
    for row_number, values in enumerate(reader, start=2):
        if _is_blank(values):
            continue
        if len(values) > len(headers):
            raise ImportFileError(
                "invalid_csv",
                f"Row {row_number} has more columns than the header",
            )
        row = {
            header: _json_value(values[index]) if index < len(values) else None
            for index, header in enumerate(headers)
        }
        rows.append((row_number, row))

    if not rows:
        raise ImportFileError("empty_file", "The uploaded file has no data rows")

    return ParsedImport(headers=headers, rows=rows, file_type="csv")


def _parse_xlsx(data: bytes) -> ParsedImport:
    try:
        workbook = load_workbook(BytesIO(data), read_only=False, data_only=True)
    except (InvalidFileException, OSError, ValueError) as exc:
        raise ImportFileError("invalid_xlsx", "The XLSX file could not be read") from exc

    try:
        worksheet = workbook.active
        if worksheet is None:
            raise ImportFileError("empty_file", "The workbook has no active sheet")

        for merged_range in worksheet.merged_cells.ranges:
            if merged_range.min_row <= 1 <= merged_range.max_row:
                raise ImportFileError(
                    "merged_headers",
                    "Merged cells in the header row are not supported; unmerge them first",
                )

        row_iterator = worksheet.iter_rows(values_only=True)
        try:
            header_row = next(row_iterator)
        except StopIteration as exc:
            raise ImportFileError("empty_file", "The uploaded file is empty") from exc

        headers = _clean_headers(list(header_row))
        rows: list[tuple[int, dict[str, Any]]] = []
        for row_number, values in enumerate(row_iterator, start=2):
            if _is_blank(values):
                continue
            if len(values) > len(headers):
                raise ImportFileError(
                    "invalid_xlsx",
                    f"Row {row_number} has more columns than the header",
                )
            row = {
                header: _json_value(values[index]) if index < len(values) else None
                for index, header in enumerate(headers)
            }
            rows.append((row_number, row))
    finally:
        workbook.close()

    if not rows:
        raise ImportFileError("empty_file", "The uploaded file has no data rows")

    return ParsedImport(headers=headers, rows=rows, file_type="xlsx")


def _clean_headers(values: list[Any] | tuple[Any, ...]) -> list[str]:
    headers = ["" if value is None else str(value).strip() for value in values]
    if not headers or not any(headers):
        raise ImportFileError("empty_headers", "The header row is empty")

    if any(not header for header in headers):
        raise ImportFileError("empty_headers", "Every column needs a header")

    folded = [header.casefold() for header in headers]
    if len(set(folded)) != len(folded):
        raise ImportFileError("duplicate_headers", "Header names must be unique")

    return headers


def _is_blank(values: tuple[Any, ...] | list[Any]) -> bool:
    return all(value is None or str(value).strip() == "" for value in values)


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, datetime | date | time):
        return value.isoformat()
    return str(value)


def _optional_text(value: Any) -> str | None:
    text = _text(value).strip()
    return text or None


def _normalise_optional_email(value: Any) -> str | None:
    raw = _optional_text(value)
    if raw is None:
        return None
    try:
        return normalise_email(raw)
    except InvalidEmail as exc:
        raise ImportRowError(exc.code, str(exc)) from exc


def _normalise_optional_phone(value: Any) -> str | None:
    raw = _optional_text(value)
    if raw is None:
        return None
    try:
        return normalise_phone(raw)
    except InvalidPhone as exc:
        raise ImportRowError(exc.code, str(exc)) from exc


def _normalise_optional_score(value: Any) -> Decimal | None:
    raw = _optional_text(value)
    if raw is None:
        return None
    try:
        return Decimal(str(normalise_score(raw)))
    except InvalidScore as exc:
        raise ImportRowError(exc.code, str(exc)) from exc


def _normalise_optional_year(value: Any) -> int | None:
    raw = _optional_text(value)
    if raw is None:
        return None

    try:
        number = Decimal(raw)
    except InvalidOperation as exc:
        raise ImportRowError("invalid_graduation_year", "Graduation year must be a year") from exc

    if not number.is_finite() or number != number.to_integral_value():
        raise ImportRowError("invalid_graduation_year", "Graduation year must be a whole year")

    year = int(number)
    if not 1900 <= year <= 2100:
        raise ImportRowError(
            "invalid_graduation_year",
            "Graduation year must be between 1900 and 2100",
        )
    return year


def _catalogue_value(value: Any, *, field: str, max_length: int) -> str | None:
    raw = _optional_text(value)
    if raw is None:
        return None

    collapsed = " ".join(raw.split())
    if len(collapsed) > max_length:
        raise ImportRowError(f"invalid_{field}", f"{field.title()} is too long")
    return collapsed


def _admission_cycle(value: Any) -> str:
    raw = _optional_text(value)
    if raw is None:
        return str(datetime.now(UTC).year)

    cycle = " ".join(raw.split())
    if len(cycle) > 32:
        raise ImportRowError("invalid_admission_cycle", "Admission cycle is too long")
    return cycle


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, datetime | date | time):
        return value.isoformat()
    return str(value)
