"""Catalogue options used by lead filters and manual entry forms."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class ProgrammeOption(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    code: str | None


class CampusOption(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    city: str | None


class LeadSourceOption(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class CatalogueRead(BaseModel):
    programmes: list[ProgrammeOption]
    campuses: list[CampusOption]
    sources: list[LeadSourceOption]
