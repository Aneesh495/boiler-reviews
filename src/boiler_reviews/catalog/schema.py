from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CatalogCourse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=2, max_length=40)
    stable_code: str | None = Field(default=None, max_length=40)
    title: str = Field(min_length=1, max_length=240)
    credits: int = Field(gt=0, le=30)
    description: str | None = None
    prerequisites: str | None = None
    availability: dict[str, Any] = Field(default_factory=dict)

    @field_validator("code", "stable_code")
    @classmethod
    def normalize_code(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else value


class CatalogTerm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=20)
    year: int = Field(ge=1900, le=2200)
    starts_on: str
    ends_on: str


class CatalogDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = "1"
    institution_code: str = Field(min_length=2, max_length=40)
    institution_name: str = Field(min_length=1, max_length=200)
    timezone: str = "America/Indiana/Indianapolis"
    version: str = Field(min_length=1, max_length=80)
    source_uri: str | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)
    courses: list[CatalogCourse] = Field(min_length=1)
    terms: list[CatalogTerm] = Field(default_factory=list)
