"""Pure consent decision rules."""

from __future__ import annotations

import uuid

from app.core.domain import ConsentCategory, ConsentChannel
from app.models.consent_record import ConsentRecord
from app.services.consent import consent_allows


def _record(granted: bool) -> ConsentRecord:
    return ConsentRecord(
        student_id=uuid.uuid4(),
        channel=ConsentChannel.EMAIL,
        category=ConsentCategory.PROMOTIONAL,
        granted=granted,
        source="web_form",
        method="checkbox",
    )


def test_promotional_without_a_record_is_blocked() -> None:
    assert consent_allows(None, ConsentCategory.PROMOTIONAL) is False


def test_transactional_without_a_record_is_allowed() -> None:
    assert consent_allows(None, ConsentCategory.TRANSACTIONAL) is True


def test_granted_record_allows_promotional_send() -> None:
    assert consent_allows(_record(True), ConsentCategory.PROMOTIONAL) is True


def test_revoked_record_blocks_promotional_send() -> None:
    assert consent_allows(_record(False), ConsentCategory.PROMOTIONAL) is False
