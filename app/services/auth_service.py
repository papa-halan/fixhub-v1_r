from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User
from app.services.passwords import verify_and_upgrade_password_hash


class AuthenticationError(ValueError):
    pass


def login(*, session: Session, email: str, password: str) -> User:
    user = session.scalar(select(User).where(User.email == email).limit(1))
    if user is None:
        raise AuthenticationError("Invalid credentials")
    if not user.is_active:
        raise AuthenticationError("User is inactive")
    password_valid, upgraded_hash = verify_and_upgrade_password_hash(user.password_hash, password)
    if not password_valid:
        raise AuthenticationError("Invalid credentials")
    if upgraded_hash is not None:
        user.password_hash = upgraded_hash
        session.flush()
    return user


def current_user(*, session: Session, user_id: uuid.UUID) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise AuthenticationError(f"User {user_id} does not exist")
    if not user.is_active:
        raise AuthenticationError(f"User {user_id} is inactive")
    return user
