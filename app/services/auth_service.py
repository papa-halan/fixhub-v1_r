from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User


class AuthenticationError(ValueError):
    pass


def login(*, session: Session, email: str, password: str) -> User:
    user = session.scalar(select(User).where(User.email == email).limit(1))
    if user is None:
        raise AuthenticationError("Invalid credentials")
    if not user.is_active:
        raise AuthenticationError("User is inactive")
    if user.password_hash != password:
        raise AuthenticationError("Invalid credentials")
    return user


def current_user(*, session: Session, user_id: uuid.UUID) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise AuthenticationError(f"User {user_id} does not exist")
    if not user.is_active:
        raise AuthenticationError(f"User {user_id} is inactive")
    return user
