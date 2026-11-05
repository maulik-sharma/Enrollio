"""A grep gate: only the messaging service may touch provider adapters (M3.3).

The plan's done-when says CI confirms no module calls provider adapters
directly except messaging. Scanning the sources keeps that true even when a
future import sneaks past review.
"""

from __future__ import annotations

import re
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]

# Provider adapter indicators. Only app code under these roots may contain
# them: the integrations package itself, its factory, and the single entry
# point that is allowed to call adapters (app/services/messaging.py).
ALLOWED_ROOTS = ("app/integrations/", "app/services/messaging.py")

PATTERNS = (
    re.compile(
        r"from\s+app\.integrations\.email\.(mock|sendgrid|resend)"
        r"|import\s+app\.integrations\.email\.(mock|sendgrid|resend)"
    ),
    re.compile(r"MockEmailProvider\(|SendGridEmailProvider\(|ResendEmailProvider\("),
    re.compile(r"app\.integrations\.whatsapp\.(stub|factory)"),
)


def test_no_provider_adapter_imports_outside_the_messaging_entry_point() -> None:
    violations: list[str] = []
    app_root = BACKEND_ROOT / "app"
    for path in sorted(app_root.rglob("*.py")):
        relative = path.relative_to(BACKEND_ROOT).as_posix()
        if relative.startswith(ALLOWED_ROOTS):
            continue
        source = path.read_text(encoding="utf-8")
        for pattern in PATTERNS:
            match = pattern.search(source)
            if match is not None:
                violations.append(f"{relative}: {match.group(0)!r}")

    assert not violations, (
        "Provider adapters may only be constructed inside the messaging entry "
        f"point; found: {violations}"
    )


def test_messaging_service_itself_imports_the_adapters() -> None:
    """Guard the guard: the allowlist entry must include the entry point."""
    source = (BACKEND_ROOT / "app/services/messaging.py").read_text(encoding="utf-8")
    assert "from app.integrations.email.base import" in source
