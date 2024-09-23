from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class ErrorBody(BaseModel):
    code: str
    message: str
    fields: dict[str, str] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorBody


class CursorPage[T](BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    items: list[T]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)
    next_cursor: str | None = None


class ReviewWrite(BaseModel):
    model_config = ConfigDict(extra='forbid')
    course_id: str
    term_id: str
    professor: str = Field(min_length=1, max_length=200)
    difficulty: int = Field(ge=1, le=5)
    workload_hours: int = Field(ge=0, le=168)
    overall: int = Field(ge=1, le=5)
    would_recommend: bool
    comment: str | None = Field(default=None, max_length=5000)


class PlanWrite(BaseModel):
    model_config = ConfigDict(extra='allow')
    courses: list[dict[str, Any]] = Field(min_length=1)
    terms: list[dict[str, Any]] = Field(min_length=1)
    requirements: list[dict[str, Any]] = Field(default_factory=list)
    pinned: dict[str, int] = Field(default_factory=dict)
    objective: str = 'earliest_completion'
    time_limit_seconds: float = Field(default=15, gt=0, le=120)


def validate_json(model: type[BaseModel], payload: Any) -> BaseModel:
    try:
        return model.model_validate(payload)
    except ValidationError as error:
        fields = {'.'.join(str(part) for part in item['loc']): item['msg'] for item in error.errors()}
        raise ValueError(json_error(fields)) from error


def json_error(fields: dict[str, str]) -> str:
    return '; '.join(f"{field}: {message}" for field, message in fields.items())
