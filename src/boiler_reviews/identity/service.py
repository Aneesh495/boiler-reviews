from __future__ import annotations

import re
from dataclasses import dataclass

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from sqlalchemy import select
from sqlalchemy.orm import Session

from boiler_reviews.common.errors import ConflictError, PermissionDenied, ValidationError
from boiler_reviews.db.models import Account, AuditEvent

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_hasher = PasswordHasher()


@dataclass(frozen=True, slots=True)
class AuthenticatedAccount:
    id: str
    email: str
    display_name: str
    roles: frozenset[str]
    synthetic: bool


def normalize_email(value: str) -> str:
    email = value.strip().casefold()
    if not _EMAIL.match(email):
        raise ValidationError("Enter a valid email address.", fields={"email": "invalid"})
    return email


def register_account(
    session: Session,
    *,
    email: str,
    password: str,
    display_name: str,
    roles: list[str] | None = None,
    synthetic: bool = True,
) -> Account:
    normalized = normalize_email(email)
    if len(password) < 12:
        raise ValidationError("Password must contain at least 12 characters.", fields={"password": "too_short"})
    name = display_name.strip()
    if not 2 <= len(name) <= 120:
        raise ValidationError("Display name must contain 2 to 120 characters.", fields={"display_name": "length"})
    if session.scalar(select(Account).where(Account.email == normalized)) is not None:
        raise ConflictError("An account with that email already exists.")
    account = Account(
        email=normalized,
        password_hash=_hasher.hash(password),
        display_name=name,
        roles_json=sorted(set(roles or [])),
        synthetic=synthetic,
    )
    session.add(account)
    session.flush()
    session.add(
        AuditEvent(
            actor_id=account.id,
            event_type="account.created",
            entity_type="account",
            entity_id=account.id,
            payload_json={"synthetic": synthetic},
        )
    )
    return account


def authenticate(session: Session, *, email: str, password: str) -> Account | None:
    normalized = normalize_email(email)
    account = session.scalar(select(Account).where(Account.email == normalized, Account.is_active.is_(True)))
    if account is None:
        return None
    try:
        _hasher.verify(account.password_hash, password)
    except (VerifyMismatchError, VerificationError):
        return None
    return account


def to_authenticated(account: Account) -> AuthenticatedAccount:
    return AuthenticatedAccount(
        id=account.id,
        email=account.email,
        display_name=account.display_name,
        roles=frozenset(account.roles_json),
        synthetic=account.synthetic,
    )


def require_role(account: Account | None, role: str) -> None:
    if account is None or role not in set(account.roles_json):
        raise PermissionDenied(f"The {role} role is required.")
