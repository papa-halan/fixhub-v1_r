from __future__ import annotations

import base64
import hashlib
import hmac
import secrets


SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value.encode("ascii"))


def hash_password(password: str) -> str:
    cleaned = password.strip()
    if not cleaned:
        raise ValueError("Password must not be empty")

    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        cleaned.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_DKLEN,
    )
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_encode(salt)}${_encode(digest)}"


def verify_password(password: str, password_hash: str | None) -> bool:
    if password_hash is None:
        return False

    algorithm, separator, remainder = password_hash.partition("$")
    if algorithm != "scrypt" or separator == "":
        return False

    try:
        n_value, r_value, p_value, salt_value, digest_value = remainder.split("$", maxsplit=4)
        expected_digest = hashlib.scrypt(
            password.encode("utf-8"),
            salt=_decode(salt_value),
            n=int(n_value),
            r=int(r_value),
            p=int(p_value),
            dklen=SCRYPT_DKLEN,
        )
    except (TypeError, ValueError):
        return False

    return hmac.compare_digest(_encode(expected_digest), digest_value)
