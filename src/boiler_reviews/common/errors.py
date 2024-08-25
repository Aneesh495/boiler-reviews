from __future__ import annotations


class DomainError(Exception):
    """Expected business-rule failure safe to expose as a structured API error."""


class NotFoundError(DomainError):
    pass


class ConflictError(DomainError):
    pass


class PermissionDenied(DomainError):
    pass


class ValidationError(DomainError):
    def __init__(self, message: str, *, fields: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.fields = fields or {}


class InfeasiblePlan(DomainError):
    pass
