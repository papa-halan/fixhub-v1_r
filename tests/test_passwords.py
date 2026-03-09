from __future__ import annotations

import unittest

from app.services.passwords import (
    hash_password,
    verify_and_upgrade_password_hash,
    verify_password,
)


class PasswordServiceTests(unittest.TestCase):
    def test_hash_password_generates_argon2_hash(self) -> None:
        password_hash = hash_password("resident-password")

        self.assertTrue(password_hash.startswith("$argon2"))
        self.assertTrue(verify_password(password_hash, "resident-password"))
        self.assertFalse(verify_password(password_hash, "wrong-password"))

    def test_verify_and_upgrade_password_hash_rehashes_legacy_plaintext(self) -> None:
        verified, upgraded_hash = verify_and_upgrade_password_hash(
            "resident-password",
            "resident-password",
        )

        self.assertTrue(verified)
        self.assertIsNotNone(upgraded_hash)
        assert upgraded_hash is not None
        self.assertTrue(upgraded_hash.startswith("$argon2"))

    def test_verify_and_upgrade_password_hash_rejects_bad_legacy_plaintext(self) -> None:
        verified, upgraded_hash = verify_and_upgrade_password_hash(
            "resident-password",
            "wrong-password",
        )

        self.assertFalse(verified)
        self.assertIsNone(upgraded_hash)
