"""Application factory is importable and returns a FastAPI app."""

from fastapi import FastAPI

from app.main import app


def test_app_object_exists() -> None:
    assert isinstance(app, FastAPI)


def test_app_has_a_title() -> None:
    assert app.title == "Enrollio Admission API"
