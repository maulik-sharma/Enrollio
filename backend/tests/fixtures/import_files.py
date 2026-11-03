"""Generators for the four M2.3 import fixtures.

Keeping them programmatic avoids committing thousands of generated rows while
still exercising real CSV and XLSX parsing.
"""

from __future__ import annotations

import csv
from io import BytesIO, StringIO
from typing import Any

from openpyxl import Workbook

HEADERS = [
    "Full Name",
    "Email",
    "Phone",
    "Course",
    "Score",
    "Graduation Year",
    "Source",
    "Campus",
    "Admission Cycle",
]

MAPPER = {
    "Full Name": "name",
    "Email": "email",
    "Phone": "phone",
    "Course": "course",
    "Score": "score",
    "Graduation Year": "graduation_year",
    "Source": "source",
    "Campus": "campus",
    "Admission Cycle": "admission_cycle",
}


def _valid_row(index: int) -> dict[str, str]:
    return {
        "Full Name": f"Student {index}",
        "Email": f"student{index}@example.com",
        "Phone": f"+9198765{index:05d}",
        "Course": "B.Tech Computer Science",
        "Score": f"{70 + index % 30}%",
        "Graduation Year": "2027",
        "Source": "Website",
        "Campus": "Main Campus",
        "Admission Cycle": "2026-fall",
    }


def mixed_rows() -> list[dict[str, str]]:
    """85 valid unique rows, 5 duplicate rows, and 10 invalid rows."""
    valid = [_valid_row(index) for index in range(1, 86)]
    duplicates = [dict(valid[index]) for index in range(5)]

    invalid = [
        {
            **_valid_row(900),
            "Full Name": "",
            "Email": "",
            "Phone": "",
        },
        {
            **_valid_row(901),
            "Email": "",
            "Phone": "",
        },
        {
            **_valid_row(902),
            "Email": "not-an-email",
            "Phone": "",
        },
        {
            **_valid_row(903),
            "Email": "",
            "Phone": "12345",
        },
        {
            **_valid_row(904),
            "Email": "badscore@example.com",
            "Phone": "",
            "Score": "abc",
        },
        {
            **_valid_row(905),
            "Email": "unknowncourse@example.com",
            "Phone": "",
            "Course": "Astrophysics",
        },
        {
            **_valid_row(906),
            "Email": "unknowncampus@example.com",
            "Phone": "",
            "Campus": "Moon Base",
        },
        {
            **_valid_row(907),
            "Email": "unknownsource@example.com",
            "Phone": "",
            "Source": "Carrier Pigeon",
        },
        {
            **_valid_row(908),
            "Email": "badyear@example.com",
            "Phone": "",
            "Graduation Year": "3000",
        },
        {
            **_valid_row(909),
            "Email": valid[0]["Email"],
            "Phone": valid[1]["Phone"],
        },
    ]

    return [*valid, *duplicates, *invalid]


def mixed_csv() -> bytes:
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=HEADERS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(mixed_rows())
    return buffer.getvalue().encode("utf-8")


def single_row_csv(**overrides: str) -> bytes:
    """One valid row with selected column values replaced."""
    row = _valid_row(1000)
    row.update(overrides)
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=HEADERS, lineterminator="\n")
    writer.writeheader()
    writer.writerow(row)
    return buffer.getvalue().encode("utf-8")


def clean_csv(count: int = 100) -> bytes:
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=HEADERS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(_valid_row(index) for index in range(1, count + 1))
    return buffer.getvalue().encode("utf-8")


def too_many_rows_csv(max_rows: int = 10_000) -> bytes:
    return clean_csv(count=max_rows + 1)


def merged_header_xlsx() -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(["Full Name", None, "Email", "Phone"])
    worksheet.merge_cells("A1:B1")
    worksheet.append(["Merged Header", None, "merged@example.com", "+919876543210"])
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def clean_xlsx() -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(HEADERS)
    row = _valid_row(1)
    worksheet.append([row[header] for header in HEADERS])
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def rows_as_dicts() -> list[dict[str, Any]]:
    return [dict(row) for row in mixed_rows()]
