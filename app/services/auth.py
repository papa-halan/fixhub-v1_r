from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import User
from app.services.passwords import verify_password


@dataclass(frozen=True)
class AuthenticationError(Exception):
    detail: str = "Invalid email or password"

    def __str__(self) -> str:
        return self.detail


def authenticate_user(
    session: Session,
    *,
    email: str,
    password: str,
    demo_mode: bool,
) -> User:
    user = session.scalar(
        select(User)
        .options(joinedload(User.organisation))
        .where(User.email == email.strip())
        .limit(1)
    )
    if user is None or not verify_password(password, user.password_hash):
        raise AuthenticationError()
    if user.is_demo_account and not demo_mode:
        raise AuthenticationError()
    return user
