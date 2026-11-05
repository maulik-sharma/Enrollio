"""Unit tests for the pure M3.3 messaging helpers."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.core.domain import ConsentCategory, MessageCategory
from app.services import messaging
from app.services.messaging import (
    consent_category_for,
    is_quiet_hours,
    next_allowed_at,
)


@pytest.mark.parametrize(
    ("hour", "start", "end", "expected"),
    [
        # Default overnight window 21 -> 9 guards late night and early morning.
        (21, 21, 9, True),
        (23, 21, 9, True),
        (0, 21, 9, True),
        (8, 21, 9, True),
        (9, 21, 9, False),
        (20, 21, 9, False),
        # A window inside one day guards only its slice.
        (12, 12, 14, True),
        (13, 12, 14, True),
        (14, 12, 14, False),
        # An empty window never quiets.
        (7, 9, 9, False),
        (21, 9, 9, False),
    ],
)
def test_is_quiet_hours(hour: int, start: int, end: int, expected: bool) -> None:
    assert is_quiet_hours(hour, start_hour=start, end_hour=end) is expected


def test_next_allowed_at_returns_now_outside_the_window() -> None:
    now = datetime(2026, 11, 5, 12, 30, tzinfo=UTC)
    assert (
        next_allowed_at(now, timezone_name="Asia/Kolkata", start_hour=21, end_hour=9)
        == now.astimezone()
    )


def test_next_allowed_at_rolls_to_the_window_end() -> None:
    # 23:00 UTC = 04:30 IST, inside the 21 -> 9 window: allowed at 09:00 IST.
    now = datetime(2026, 11, 5, 23, 0, tzinfo=UTC)
    allowed = next_allowed_at(now, timezone_name="Asia/Kolkata", start_hour=21, end_hour=9)
    assert allowed.hour == 9
    assert allowed.minute == 0
    offset = allowed.utcoffset()
    assert offset is not None
    assert offset.total_seconds() == 5.5 * 3600


def test_next_allowed_at_rolls_to_the_next_day_when_past_the_end_hour() -> None:
    # 18:00 UTC = 23:30 IST, inside the wrapped 21 -> 9 window: allowed at
    # 09:00 IST on the following day.
    now = datetime(2026, 11, 5, 18, 0, tzinfo=UTC)
    allowed = next_allowed_at(now, timezone_name="Asia/Kolkata", start_hour=21, end_hour=9)
    assert allowed.hour == 9
    assert allowed.day == now.day + 1


def test_next_allowed_at_rejects_an_unknown_timezone() -> None:
    now = datetime(2026, 11, 5, 12, 30, tzinfo=UTC)
    with pytest.raises(messaging.MessagingError):
        next_allowed_at(now, timezone_name="Mars/Olympus", start_hour=21, end_hour=9)


@pytest.mark.parametrize(
    ("category", "expected"),
    [
        (MessageCategory.TRANSACTIONAL, "transactional"),
        (MessageCategory.PROMOTIONAL, "promotional"),
        (MessageCategory.SCHOLARSHIP, "transactional"),
        (MessageCategory.FEE, "transactional"),
        (MessageCategory.ADMISSION_OFFER, "transactional"),
        (MessageCategory.DEADLINE_CHANGE, "transactional"),
    ],
)
def test_consent_category_for(category: MessageCategory, expected: str) -> None:
    assert consent_category_for(category) is ConsentCategory(expected)


def test_sensitive_categories_match_the_plan() -> None:
    assert (
        frozenset(
            {
                MessageCategory.SCHOLARSHIP,
                MessageCategory.FEE,
                MessageCategory.ADMISSION_OFFER,
                MessageCategory.DEADLINE_CHANGE,
            }
        )
        == messaging.SENSITIVE_CATEGORIES
    )
