from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class Expr:
    def as_dict(self) -> dict[str, Any]:
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class CourseRef(Expr):
    code: str

    def as_dict(self) -> dict[str, Any]:
        return {"type": "course", "code": self.code}


@dataclass(frozen=True, slots=True)
class AllOf(Expr):
    items: tuple[Expr, ...]

    def as_dict(self) -> dict[str, Any]:
        return {"type": "and", "items": [item.as_dict() for item in self.items]}


@dataclass(frozen=True, slots=True)
class AnyOf(Expr):
    items: tuple[Expr, ...]

    def as_dict(self) -> dict[str, Any]:
        return {"type": "or", "items": [item.as_dict() for item in self.items]}


@dataclass(frozen=True, slots=True)
class GradeAtLeast(Expr):
    course: CourseRef
    grade: str

    def as_dict(self) -> dict[str, Any]:
        return {"type": "grade", "course": self.course.as_dict(), "grade": self.grade}


@dataclass(frozen=True, slots=True)
class CreditsAtLeast(Expr):
    credits: int

    def as_dict(self) -> dict[str, Any]:
        return {"type": "credits", "credits": self.credits}


@dataclass(frozen=True, slots=True)
class Predicate(Expr):
    kind: str
    value: str

    def as_dict(self) -> dict[str, Any]:
        return {"type": self.kind, "value": self.value}


@dataclass(frozen=True, slots=True)
class CoRequisite(Expr):
    items: tuple[Expr, ...]

    def as_dict(self) -> dict[str, Any]:
        return {"type": "corequisite", "items": [item.as_dict() for item in self.items]}


def expr_from_dict(value: dict[str, Any]) -> Expr:
    kind = value.get("type")
    if kind == "course":
        return CourseRef(str(value["code"]))
    if kind == "and":
        return AllOf(tuple(expr_from_dict(item) for item in value.get("items", [])))
    if kind == "or":
        return AnyOf(tuple(expr_from_dict(item) for item in value.get("items", [])))
    if kind == "grade":
        course = expr_from_dict(value["course"])
        if not isinstance(course, CourseRef):
            raise ValueError("grade expression must point to a course")
        return GradeAtLeast(course, str(value["grade"]))
    if kind == "credits":
        return CreditsAtLeast(int(value["credits"]))
    if kind in {"placement", "permission"}:
        return Predicate(kind, str(value["value"]))
    if kind == "corequisite":
        return CoRequisite(tuple(expr_from_dict(item) for item in value.get("items", [])))
    raise ValueError(f"unknown prerequisite AST node: {kind}")
