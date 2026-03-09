from __future__ import annotations

from hmac import compare_digest

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError


_PASSWORD_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Password must not be empty")
    return _PASSWORD_HASHER.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    verified, _ = verify_and_upgrade_password_hash(password_hash, password)
    return verified


def verify_and_upgrade_password_hash(password_hash: str, password: str) -> tuple[bool, str | None]:
    if not password_hash or not password:
        return False, None

    if _looks_like_argon2_hash(password_hash):
        try:
            _PASSWORD_HASHER.verify(password_hash, password)
        except (VerifyMismatchError, InvalidHashError, VerificationError):
            return False, None

        if _PASSWORD_HASHER.check_needs_rehash(password_hash):
            return True, hash_password(password)
        return True, None

    # Legacy plaintext fallback only exists to upgrade existing local-dev seed rows.
    if compare_digest(password_hash, password):
        return True, hash_password(password)
    return False, None


def _looks_like_argon2_hash(password_hash: str) -> bool:
    return password_hash.startswith("$argon2")
