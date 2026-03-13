from __future__ import annotations

import os
from dataclasses import dataclass


def default_database_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/fixhub",
    )


@dataclass(frozen=True)
class Settings:
    app_name: str = "FixHub"
    database_url: str = default_database_url()
    default_user_email: str = os.getenv("FIXHUB_DEFAULT_USER", "resident@fixhub.test")


settings = Settings()
