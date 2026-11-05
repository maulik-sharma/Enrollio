"""Unit tests for the M3.4 template renderer."""

from __future__ import annotations

import pytest

from app.core.domain import MessageCategory, MessageChannel
from app.models.message_template import MessageTemplate
from app.services.templates import (
    PLACEHOLDERS,
    TemplateRenderError,
    append_unsubscribe_text,
    referenced_placeholders,
    render,
    render_template,
)

CONTEXT = {
    "first_name": "Asha",
    "last_name": "Rao",
    "programme": "B.Tech CSE",
    "campus": "Bengaluru",
    "deadline": "30 November 2026",
    "counsellor_name": "Meera Iyer",
    "admission_cycle": "2026-fall",
    "application_link": "https://apply.example/asha",
}


def test_all_fields_present_produce_expected_output() -> None:
    rendered = render(
        "Hi {{first_name}}, {{programme}} at {{campus}}",
        "Dear {{first_name}}, your deadline is {{deadline}}.\nContact {{counsellor_name}}.",
        CONTEXT,
        category=MessageCategory.TRANSACTIONAL,
    )
    assert rendered.subject == "Hi Asha, B.Tech CSE at Bengaluru"
    assert rendered.text_body == (
        "Dear Asha, your deadline is 30 November 2026.\nContact Meera Iyer."
    )
    assert rendered.used_placeholders == frozenset(
        {"first_name", "programme", "campus", "deadline", "counsellor_name"}
    )


def test_lone_braces_and_extra_context_are_ignored() -> None:
    rendered = render(
        "Hello {{first_name}} {not_a_placeholder} anycas",
        "Thanks, {{first_name}}!",
        CONTEXT,
        category=MessageCategory.TRANSACTIONAL,
    )
    assert rendered.text_body == "Thanks, Asha!"
    assert rendered.subject == "Hello Asha {not_a_placeholder} anycas"


def test_whitespace_around_placeholders_is_tolerated() -> None:
    rendered = render(
        "Hi {{ first_name }}",
        "See you,\n{{ counsellor_name }}",
        CONTEXT,
        category=MessageCategory.TRANSACTIONAL,
    )
    assert rendered.subject == "Hi Asha"


def test_repeated_placeholders_are_replaced_everywhere() -> None:
    rendered = render(
        "{{first_name}}",
        "{{first_name}}, {{first_name}}, and again {{first_name}}!",
        CONTEXT,
        category=MessageCategory.TRANSACTIONAL,
    )
    assert rendered.text_body == "Asha, Asha, and again Asha!"


def test_single_missing_field_is_listed() -> None:
    context = {key: value for key, value in CONTEXT.items() if key != "deadline"}
    with pytest.raises(TemplateRenderError) as error:
        render(
            "Deadline",
            "Your deadline is {{deadline}}.",
            context,
            category=MessageCategory.TRANSACTIONAL,
        )
    assert error.value.missing == ["deadline"]
    assert "{{deadline}}" in str(error.value)


def test_all_missing_fields_are_listed_together() -> None:
    with pytest.raises(TemplateRenderError) as error:
        render(
            "Hi {{first_name}}",
            "{{deadline}} for {{campus}}, reply to {{counsellor_name}}",
            {},
            category=MessageCategory.TRANSACTIONAL,
        )
    assert error.value.missing == ["campus", "counsellor_name", "deadline", "first_name"]
    assert error.value.unsupported == []


def test_blank_values_count_as_missing() -> None:
    with pytest.raises(TemplateRenderError) as error:
        render(
            "Hi",
            "For {{programme}}",
            {**CONTEXT, "programme": "   "},
            category=MessageCategory.TRANSACTIONAL,
        )
    assert error.value.missing == ["programme"]


def test_unsupported_placeholders_are_rejected() -> None:
    with pytest.raises(TemplateRenderError) as error:
        render(
            "Hi {{first_nam}}",
            "body",
            CONTEXT,
            category=MessageCategory.TRANSACTIONAL,
        )
    assert error.value.unsupported == ["first_nam"]


def test_placeholder_whitelist_is_closed() -> None:
    assert "first_name" in PLACEHOLDERS
    assert "unsubscribe_url" not in PLACEHOLDERS


def test_promotional_render_appends_the_unsubscribe_link() -> None:
    rendered = render(
        "Open house invitation",
        "Join us {{first_name}}!",
        CONTEXT,
        category=MessageCategory.PROMOTIONAL,
        unsubscribe_url="https://enrollio.example/unsub/abc",
    )
    assert "Unsubscribe: https://enrollio.example/unsub/abc" in rendered.text_body
    assert "unsubscribe_url" in rendered.used_placeholders


def test_promotional_html_links_the_unsubscribe_url() -> None:
    rendered = render(
        "Open house",
        "Join us {{first_name}}!",
        CONTEXT,
        category=MessageCategory.PROMOTIONAL,
        unsubscribe_url="https://enrollio.example/unsub/abc",
    )
    assert '<a href="https://enrollio.example/unsub/abc">Unsubscribe</a>' in rendered.html_body


def test_transactional_render_has_no_unsubscribe_link() -> None:
    rendered = render(
        "Reminder",
        "Your session is {{deadline}}.",
        CONTEXT,
        category=MessageCategory.TRANSACTIONAL,
    )
    assert "Unsubscribe" not in rendered.subject
    assert "Unsubscribe" not in rendered.text_body
    assert "Unsubscribe" not in rendered.html_body


def test_html_variant_escapes_student_supplied_values() -> None:
    rendered = render(
        "Hi {{first_name}}",
        "Congrats {{first_name}} {{last_name}}!",
        {
            **CONTEXT,
            "first_name": 'Asha <script>alert("x")</script>',
        },
        category=MessageCategory.TRANSACTIONAL,
    )
    assert "<script>" not in rendered.html_body
    assert "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;" in rendered.html_body
    assert "<html><body>" in rendered.html_body and "</body></html>" in rendered.html_body
    # The plain-text variant keeps the raw value: text is not markup.
    assert '<script>alert("x")</script>' in rendered.text_body


def test_html_variant_escapes_multiline_and_keeps_breaks() -> None:
    rendered = render(
        "Hi",
        "Line one\nLine <b>two</b>",
        CONTEXT,
        category=MessageCategory.TRANSACTIONAL,
    )
    assert "Line one<br/>Line &lt;b&gt;two&lt;/b&gt;" in rendered.html_body


def test_append_unsubscribe_is_idempotent_and_dataclass_render() -> None:
    base = "Hello"
    link = "https://enrollio.example/u"
    once = append_unsubscribe_text(base, link)
    twice = append_unsubscribe_text(once, link)
    assert once == f"Hello\n\nUnsubscribe: {link}"
    assert once == twice


def test_render_template_uses_the_row_category() -> None:
    template = MessageTemplate(
        name="Offer letter",
        channel=MessageChannel.EMAIL,
        category=MessageCategory.PROMOTIONAL,
        subject="Offer for {{programme}}",
        body="Well done {{first_name}}, {{campus}} awaits.",
    )
    rendered = render_template(template, CONTEXT, unsubscribe_url="https://enrollio.example/u")
    assert rendered.subject == "Offer for B.Tech CSE"
    assert "Unsubscribe: https://enrollio.example/u" in rendered.text_body


def test_referenced_placeholders_can_double_check_templates() -> None:
    assert referenced_placeholders("{{deadline}}", "for {{campus}}") == {"campus", "deadline"}
    assert referenced_placeholders("no references", "plain") == set()
