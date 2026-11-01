"""FastAPI application entry point."""

from fastapi import FastAPI

from app import __version__


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    return FastAPI(title="Enrollio Admission API", version=__version__)


app = create_app()
