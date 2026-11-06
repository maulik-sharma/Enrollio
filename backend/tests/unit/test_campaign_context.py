"""Unit tests for the campaign recipient render context (M3.5)."""

from __future__ import annotations

from datetime import UTC, datetime

from app.core.domain import LifecycleStatus
from app.models.campus import Campus
from app.models.lead import Lead
from app.models.programme import Programme
from app.models.student import Student
from app.models.user import User
from app.services.campaigns import recipient_context


def test_context_includes_every_assigned_field() -> None:
    student = Student(
        first_name="Asha",
        last_name="Rao",
        email_normalised="asha@example.com",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    lead = Lead(
        student=student,
        admission_cycle="2026-fall",
        lifecycle_status=LifecycleStatus.NEW_ENQUIRY,
        programme=Programme(name="B.Tech CSE"),
        campus=Campus(name="Main Campus"),
        assigned_counsellor=User(full_name="Meera Iyer"),
    )
    context = recipient_context(lead)
    assert context == {
        "first_name": "Asha",
        "last_name": "Rao",
        "email": "asha@example.com",
        "programme": "B.Tech CSE",
        "campus": "Main Campus",
        "counsellor_name": "Meera Iyer",
        "admission_cycle": "2026-fall",
    }


def test_context_drops_absent_optional_fields_so_render_reports_them() -> None:
    import uuid as uuid_module

    student = Student(first_name="Ravi", last_name="K", email_normalised=None)
    lead = Lead(
        id=uuid_module.uuid4(),
        student=student,
        student_id=uuid_module.uuid4(),
        admission_cycle="2026-fall",
        lifecycle_status=LifecycleStatus.NEW_ENQUIRY,
    )
    context = recipient_context(lead)
    assert set(context) == {"first_name", "last_name", "admission_cycle"}
    assert "programme" not in context  # renderer reports {{programme}} missing
    assert "counsellor_name" not in context
