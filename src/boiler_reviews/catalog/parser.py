from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from boiler_reviews.catalog.ast import (
    AllOf,
    AnyOf,
    CoRequisite,
    CourseRef,
    CreditsAtLeast,
    Expr,
    GradeAtLeast,
    Predicate,
)


@dataclass(frozen=True, slots=True)
class Token:
    kind: str
    value: str
    position: int


@dataclass(frozen=True, slots=True)
class Diagnostic:
    code: str
    message: str
    position: int


@dataclass(frozen=True, slots=True)
class ParseResult:
    status: str
    ast: Expr | None
    diagnostics: tuple[Diagnostic, ...]
    tokens: tuple[Token, ...]


_TOKEN = re.compile(
    r"(?P<SPACE>\s+)|(?P<AND>AND\b)|(?P<OR>OR\b)|(?P<COREQ>COREQ\b)|"
    r"(?P<LPAREN>\()|(?P<RPAREN>\))|(?P<COMMA>,)|"
    r"(?P<CREDITS>CREDITS\s*>=\s*(?P<credit_value>\d+))|"
    r"(?P<GRADE>GRADE\s*>=\s*(?P<grade_value>[A-Fa-f][+-]?))|"
    r"(?P<PLACEMENT>PLACEMENT\s*\((?P<placement_value>[^)]*)\))|"
    r"(?P<PERMISSION>PERMISSION\s*\((?P<permission_value>[^)]*)\))|"
    r"(?P<COURSE>[A-Za-z]{2,8}\s*[- ]?\s*\d{2,4}[A-Za-z]?)"
)


def normalize_course_code(value: str) -> str:
    return re.sub(r"[\s-]+", "", value).upper()


def tokenize(source: str) -> tuple[Token, ...]:
    tokens: list[Token] = []
    position = 0
    while position < len(source):
        match = _TOKEN.match(source, position)
        if match is None:
            raise ValueError(f"unsupported prerequisite syntax at position {position}")
        kind = match.lastgroup or ""
        if kind != "SPACE":
            tokens.append(Token(kind, match.group(0).strip(), position))
        position = match.end()
    return tuple(tokens)


class _Parser:
    def __init__(self, tokens: tuple[Token, ...]) -> None:
        self.tokens = tokens
        self.index = 0
        self.diagnostics: list[Diagnostic] = []

    def current(self) -> Token | None:
        return self.tokens[self.index] if self.index < len(self.tokens) else None

    def accept(self, kind: str) -> Token | None:
        token = self.current()
        if token is not None and token.kind == kind:
            self.index += 1
            return token
        return None

    def require(self, kind: str) -> Token:
        token = self.accept(kind)
        if token is None:
            current = self.current()
            position = current.position if current else -1
            raise ValueError(f"expected {kind} at position {position}")
        return token

    def parse(self) -> Expr:
        expression = self.parse_or()
        if self.current() is not None:
            token = self.current()
            raise ValueError(f"unexpected {token.value!r} at position {token.position}")
        return expression

    def parse_or(self) -> Expr:
        items = [self.parse_and()]
        while self.accept("OR") is not None:
            items.append(self.parse_and())
        return items[0] if len(items) == 1 else AnyOf(tuple(items))

    def parse_and(self) -> Expr:
        items = [self.parse_primary()]
        while self.accept("AND") is not None:
            items.append(self.parse_primary())
        return items[0] if len(items) == 1 else AllOf(tuple(items))

    def parse_primary(self) -> Expr:
        if self.accept("LPAREN") is not None:
            expression = self.parse_or()
            self.require("RPAREN")
            return expression
        if self.accept("COREQ") is not None:
            self.require("LPAREN")
            items = [self.parse_or()]
            while self.accept("COMMA") is not None:
                items.append(self.parse_or())
            self.require("RPAREN")
            return CoRequisite(tuple(items))
        token = self.current()
        if token is None:
            raise ValueError("expected prerequisite expression at end of input")
        if token.kind == "CREDITS":
            self.index += 1
            return CreditsAtLeast(int(re.search(r"\d+", token.value).group(0)))
        if token.kind in {"PLACEMENT", "PERMISSION"}:
            self.index += 1
            value = token.value[token.value.find("(") + 1 : -1].strip()
            return Predicate(token.kind.lower(), value)
        if token.kind != "COURSE":
            raise ValueError(f"expected course or predicate at position {token.position}")
        self.index += 1
        course = CourseRef(normalize_course_code(token.value))
        grade = self.accept("GRADE")
        if grade is None:
            return course
        grade_value = re.search(r"[A-Fa-f][+-]?", grade.value)
        return GradeAtLeast(course, grade_value.group(0).upper() if grade_value else "B")


def parse_prerequisites(source: str | None) -> ParseResult:
    original = (source or "").strip()
    if not original or original.upper() in {"NONE", "N/A"}:
        return ParseResult("parsed", AllOf(tuple()), tuple(), tuple())
    try:
        tokens = tokenize(original)
        ast = _Parser(tokens).parse()
        return ParseResult("parsed", ast, tuple(), tokens)
    except ValueError as error:
        diagnostic = Diagnostic("unsupported_syntax", str(error), 0)
        return ParseResult("unsupported", None, (diagnostic,), tuple())


def ast_to_json(result: ParseResult) -> dict[str, Any] | None:
    return result.ast.as_dict() if result.ast is not None else None
