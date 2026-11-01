"""Integration test: endpoint logs never contain raw PII."""

from __future__ import annotations

import io
import json
import logging

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.logging import configure_logging
from app.main import create_app

pytestmark = pytest.mark.integration

logger = logging.getLogger("tests.pii")


def test_endpoint_payload_is_masked_in_logs() -> None:
    settings = Settings()
    app = create_app(settings)
    stream = io.StringIO()
    configure_logging(settings, stream=stream)

    @app.post("/_test/log")
    async def log_payload(payload: dict[str, str]) -> dict[str, str]:
        logger.info(
            "enquiry received",
            extra={
                "payload": f"email={payload['email']} phone={payload['phone']}",
                "notes": payload["notes"],
            },
        )
        return {"status": "logged"}

    raw_email = "rahul.sharma@gmail.com"
    raw_phone = "+919876543210"

    with TestClient(app) as client:
        response = client.post(
            "/_test/log",
            json={"email": raw_email, "phone": raw_phone, "notes": "wants a scholarship"},
            headers={"X-Request-ID": "test-request-1"},
        )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "test-request-1"

    output = stream.getvalue()
    records = [json.loads(line) for line in output.splitlines() if line.strip()]

    assert raw_email not in output
    assert "9876543210" not in output
    assert "wants a scholarship" not in output

    assert any(record["message"] == "enquiry received" for record in records)
    assert "r***@gmail.com" in output
    assert "98XXXX3210" in output
    assert any(record.get("notes") == "[REDACTED]" for record in records)
    assert any(record.get("request_id") == "test-request-1" for record in records)


def test_request_id_is_generated_when_absent() -> None:
    app = create_app(Settings())

    with TestClient(app) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert len(response.headers["X-Request-ID"]) == 32
