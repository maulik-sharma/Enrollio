"""Exact contact matching decisions for M2.4."""

from __future__ import annotations

import uuid

import pytest

from app.services.deduplication import MatchKind, decide_match

EMAIL_STUDENT = uuid.uuid4()
PHONE_STUDENT = uuid.uuid4()
NAME_STUDENT = uuid.uuid4()


def test_email_only_match_links_the_student() -> None:
    decision = decide_match(
        email_student_id=EMAIL_STUDENT,
        phone_student_id=None,
        name_student_id=NAME_STUDENT,
    )

    assert decision.kind is MatchKind.MATCHED
    assert decision.student_id == EMAIL_STUDENT


def test_phone_only_match_links_the_student() -> None:
    decision = decide_match(
        email_student_id=None,
        phone_student_id=PHONE_STUDENT,
        name_student_id=None,
    )

    assert decision.kind is MatchKind.MATCHED
    assert decision.student_id == PHONE_STUDENT


def test_both_contacts_matching_the_same_student_is_a_match() -> None:
    decision = decide_match(
        email_student_id=EMAIL_STUDENT,
        phone_student_id=EMAIL_STUDENT,
        name_student_id=None,
    )

    assert decision.kind is MatchKind.MATCHED
    assert decision.student_id == EMAIL_STUDENT
    assert decision.conflicting_student_id is None


def test_email_and_phone_matching_different_students_is_a_conflict() -> None:
    decision = decide_match(
        email_student_id=EMAIL_STUDENT,
        phone_student_id=PHONE_STUDENT,
        name_student_id=None,
    )

    assert decision.kind is MatchKind.CONFLICTING_CONTACT
    assert decision.student_id == EMAIL_STUDENT
    assert decision.conflicting_student_id == PHONE_STUDENT


def test_name_only_match_is_flagged_not_merged() -> None:
    decision = decide_match(
        email_student_id=None,
        phone_student_id=None,
        name_student_id=NAME_STUDENT,
    )

    assert decision.kind is MatchKind.NAME_ONLY
    assert decision.student_id == NAME_STUDENT


@pytest.mark.parametrize(
    ("email_student_id", "phone_student_id", "name_student_id"),
    [(None, None, None)],
)
def test_no_match_creates_a_new_student(
    email_student_id: uuid.UUID | None,
    phone_student_id: uuid.UUID | None,
    name_student_id: uuid.UUID | None,
) -> None:
    decision = decide_match(
        email_student_id=email_student_id,
        phone_student_id=phone_student_id,
        name_student_id=name_student_id,
    )

    assert decision.kind is MatchKind.NONE
    assert decision.student_id is None
