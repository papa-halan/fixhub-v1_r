from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def default_database_url() -> str:
    database_path = (ROOT_DIR / "fixhub.db").as_posix()
    return os.getenv("DATABASE_URL", f"sqlite:///{database_path}")


@dataclass(frozen=True)
class Settings:
    app_name: str
    database_url: str
    session_cookie_name: str
    session_secret: str
    demo_mode: bool
    allow_header_auth: bool
    seed_demo_data: bool
    demo_password: str


def load_settings(
    *,
    database_url: str | None = None,
    demo_mode: bool | None = None,
    allow_header_auth: bool | None = None,
    seed_demo_data: bool | None = None,
    demo_password: str | None = None,
) -> Settings:
    resolved_demo_mode = demo_mode if demo_mode is not None else env_flag("FIXHUB_DEMO_MODE", False)
    return Settings(
        app_name=os.getenv("FIXHUB_APP_NAME", "FixHub"),
        database_url=database_url or default_database_url(),
        session_cookie_name=os.getenv("FIXHUB_SESSION_COOKIE_NAME", "fixhub_session"),
        session_secret=os.getenv("FIXHUB_SESSION_SECRET", "fixhub-dev-session-secret"),
        demo_mode=resolved_demo_mode,
        allow_header_auth=(
            allow_header_auth
            if allow_header_auth is not None
            else env_flag("FIXHUB_ALLOW_HEADER_AUTH", resolved_demo_mode)
        ),
        seed_demo_data=(
            seed_demo_data
            if seed_demo_data is not None
            else env_flag("FIXHUB_SEED_DEMO_DATA", resolved_demo_mode)
        ),
        demo_password=demo_password or os.getenv("FIXHUB_DEMO_PASSWORD", "fixhub-demo-password"),
    )


settings = load_settings()
