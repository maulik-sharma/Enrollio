"""Template rendering (M3.4).

Templates store `{{placeholder}}` references in their subject and body.
Rendering is pure: given a context it returns a `RenderedMessage` with plain
text and HTML variants, failing with **every** missing field listed instead of
producing a partial message (AC5.2). Context values are HTML-escaped in the
HTML variant so student-supplied names cannot inject markup, and promotional
renders automatically carry the unsubscribe link (AC4.2).
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from typing import Any

from app.core.domain import MessageCategory
from app.models.message_template import MessageTemplate

PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([a-z][a-z0-9_]*)\s*\}\}")

#: Placeholders a template may reference. Other names are rejected at render
#: time so a typo (`{{first_nam}}`) fails loudly instead of silently sending.
PLACEHOLDERS: frozenset[str] = frozenset(
    {
        "first_name",
        "last_name",
        "programme",
        "campus",
        "deadline",
        "counsellor_name",
        "admission_cycle",
        "application_link",
    }
)

UNSUBSCRIBE_TEXT_FOOTER = "\n\nUnsubscribe: {url}"
UNSUBSCRIBE_HTML_MARKUP = '<p><a href="{href}">Unsubscribe</a></p>'


class TemplateRenderError(Exception):
    """A template cannot be rendered for one recipient."""

    def __init__(self, message: str, *, missing: list[str], unsupported: list[str]) -> None:
        super().__init__(message)
        self.message = message
        self.missing = missing
        self.unsupported = unsupported


@dataclass(frozen=True)
class RenderedMessage:
    """What one template render produces for one recipient."""

    subject: str
    text_body: str
    html_body: str
    used_placeholders: frozenset[str] = field(default_factory=frozenset)


def referenced_placeholders(*sources: str) -> set[str]:
    """Every placeholder name a subject/body references."""
    names: set[str] = set()
    for source in sources:
        names.update(match.group(1) for match in PLACEHOLDER_PATTERN.finditer(source))
    return names


def render(
    subject: str,
    body: str,
    context: dict[str, Any],
    *,
    category: MessageCategory,
    unsubscribe_url: str | None = None,
) -> RenderedMessage:
    """Render a subject/body pair, or raise with all problems listed.

    Missing context values and whitelisting violations are collected together;
    validation never mixes a refusal with a partially substituted message.
    """
    names = referenced_placeholders(subject, body)
    unsupported = sorted(name for name in names if name not in PLACEHOLDERS)
    missing = sorted(
        name
        for name in names
        if name in PLACEHOLDERS and (context.get(name) is None or str(context[name]).strip() == "")
    )
    if unsupported or missing:
        problems: list[str] = []

        def ref(name: str) -> str:
            return "{{" + name + "}}"

        if missing:
            problems.append("missing values: " + ", ".join(ref(name) for name in missing))
        if unsupported:
            problems.append(
                "unsupported placeholders: " + ", ".join(ref(name) for name in unsupported)
            )
        raise TemplateRenderError("; ".join(problems), missing=missing, unsupported=unsupported)

    used = names

    subject_ref_values = {name: str(context[name]) for name in names}
    body_ref_values = dict(subject_ref_values)

    body_footer = ""
    html_footer = ""
    if category is MessageCategory.PROMOTIONAL:
        rendered_url = unsubscribe_url or ""
        body_footer = UNSUBSCRIBE_TEXT_FOOTER.format(url=rendered_url)
        html_footer = UNSUBSCRIBE_HTML_MARKUP.format(href=rendered_url)
        used = used | {"unsubscribe_url"}

    text_subject = _substitute(subject, subject_ref_values)
    text_body = _substitute(body, body_ref_values) + body_footer
    html_body = _html_variant(_substitute(body, body_ref_values), html_footer)
    return RenderedMessage(
        subject=text_subject,
        text_body=text_body,
        html_body=html_body,
        used_placeholders=frozenset(used),
    )


def render_template(
    template: MessageTemplate,
    context: dict[str, Any],
    *,
    unsubscribe_url: str | None = None,
) -> RenderedMessage:
    """Render a stored template row."""
    return render(
        template.subject,
        template.body,
        context,
        category=template.category,
        unsubscribe_url=unsubscribe_url,
    )


def _substitute(source: str, values: dict[str, str]) -> str:
    return PLACEHOLDER_PATTERN.sub(lambda match: values[match.group(1)], source)


def _html_variant(text_body: str, extra_markup: str = "") -> str:
    paragraphs = "<br/>".join(html.escape(line) for line in text_body.splitlines())
    return f"<html><body>{paragraphs}{extra_markup}</body></html>"


def append_unsubscribe_text(source: str, unsubscribe_url: str) -> str:
    """Append the unsubscribe footer to a finished text message, idempotently."""
    if f"Unsubscribe: {unsubscribe_url}" in source:
        return source
    return source + UNSUBSCRIBE_TEXT_FOOTER.format(url=unsubscribe_url)


__all__ = [
    "PLACEHOLDERS",
    "PLACEHOLDER_PATTERN",
    "RenderedMessage",
    "TemplateRenderError",
    "append_unsubscribe_text",
    "referenced_placeholders",
    "render",
    "render_template",
]
