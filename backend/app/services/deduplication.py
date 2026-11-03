"""Exact contact matching and duplicate-candidate decisions."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import StrEnum


class MatchKind(StrEnum):
    """The outcome of comparing incoming contacts with existing students."""

    MATCHED = "matched"
    NAME_ONLY = "name_only"
    CONFLICTING_CONTACT = "conflicting_contact"
    NONE = "none"


@dataclass(frozen=True)
class MatchDecision:
    """Which existing student an incoming row belongs to, if any."""

    kind: MatchKind
    student_id: uuid.UUID | None = None
    conflicting_student_id: uuid.UUID | None = None


def decide_match(
    *,
    email_student_id: uuid.UUID | None,
    phone_student_id: uuid.UUID | None,
    name_student_id: uuid.UUID | None,
) -> MatchDecision:
    """Resolve exact email/phone matches, then fall back to a name-only flag.

    Email and phone pointing at different students is a conflict: merging could
    destroy history, so the row is flagged instead. A name-only hit is also
    flagged, never merged automatically (AC2.5).
    """
    if (
        email_student_id is not None
        and phone_student_id is not None
        and email_student_id != phone_student_id
    ):
        return MatchDecision(
            kind=MatchKind.CONFLICTING_CONTACT,
            student_id=email_student_id,
            conflicting_student_id=phone_student_id,
        )

    contact_student_id = email_student_id or phone_student_id
    if contact_student_id is not None:
        return MatchDecision(kind=MatchKind.MATCHED, student_id=contact_student_id)

    if name_student_id is not None:
        return MatchDecision(kind=MatchKind.NAME_ONLY, student_id=name_student_id)

    return MatchDecision(kind=MatchKind.NONE)
