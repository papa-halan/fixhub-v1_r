from __future__ import annotations

import unittest
import uuid

from app.models import User, UserRole
from app.services.auth_service import AuthenticationError, login
from app.services.passwords import hash_password


class LoginSession:
    def __init__(self, user: User | None) -> None:
        self.user = user
        self.flush_calls = 0

    def scalar(self, _statement: object) -> User | None:
        return self.user

    def flush(self) -> None:
        self.flush_calls += 1


def make_user(*, password_hash: str, is_active: bool = True) -> User:
    return User(
        user_id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        email="resident@uon.example",
        password_hash=password_hash,
        role=UserRole.resident,
        is_active=is_active,
    )


class AuthenticationServiceTests(unittest.TestCase):
    def test_login_accepts_hashed_password(self) -> None:
        session = LoginSession(make_user(password_hash=hash_password("resident-password")))

        user = login(
            session=session,
            email="resident@uon.example",
            password="resident-password",
        )

        self.assertEqual(user.email, "resident@uon.example")
        self.assertEqual(session.flush_calls, 0)

    def test_login_rejects_wrong_password(self) -> None:
        session = LoginSession(make_user(password_hash=hash_password("resident-password")))

        with self.assertRaisesRegex(AuthenticationError, "Invalid credentials"):
            login(
                session=session,
                email="resident@uon.example",
                password="wrong-password",
            )

    def test_login_upgrades_legacy_plaintext_passwords(self) -> None:
        session = LoginSession(make_user(password_hash="resident-password"))

        user = login(
            session=session,
            email="resident@uon.example",
            password="resident-password",
        )

        self.assertNotEqual(user.password_hash, "resident-password")
        self.assertTrue(user.password_hash.startswith("$argon2"))
        self.assertEqual(session.flush_calls, 1)
