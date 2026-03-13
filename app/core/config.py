from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = "FixHub"
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./fixhub.db")
    default_user_email: str = os.getenv("FIXHUB_DEFAULT_USER", "resident@fixhub.test")


settings = Settings()
