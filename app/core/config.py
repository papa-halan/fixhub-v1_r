from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/fixhub",
    )
    event_source: str = os.getenv("EVENT_SOURCE", "fixhub.coord")


settings = Settings()