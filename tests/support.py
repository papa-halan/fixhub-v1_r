from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.core.config import Settings, load_settings
from app.main import create_app


ROOT_DIR = Path(__file__).resolve().parents[1]
TEST_SESSION_SECRET = "fixhub-test-session-secret"
DEMO_PASSWORD = "fixhub-demo-password"


def sqlite_database_url(path: Path) -> str:
    return f"sqlite+pysqlite:///{path.resolve().as_posix()}"


def alembic_config(database_url: str) -> Config:
    config = Config(str(ROOT_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    config.attributes["database_url_explicit"] = True
    return config


def migrate_to_head(database_url: str) -> None:
    command.upgrade(alembic_config(database_url), "head")


def downgrade_to_base(database_url: str) -> None:
    command.downgrade(alembic_config(database_url), "base")


def build_settings(
    database_url: str,
    *,
    demo_mode: bool = True,
    seed_demo_data: bool | None = None,
) -> Settings:
    base_settings = load_settings()
    resolved_seed_demo_data = demo_mode if seed_demo_data is None else seed_demo_data
    return replace(
        base_settings,
        app_name="FixHub Test",
        database_url=database_url,
        session_secret=TEST_SESSION_SECRET,
        demo_mode=demo_mode,
        seed_demo_data=resolved_seed_demo_data,
        demo_password=DEMO_PASSWORD,
    )


def build_app(
    tmp_path: Path,
    *,
    demo_mode: bool = True,
    seed_demo_data: bool | None = None,
):
    database_url = sqlite_database_url(tmp_path / "fixhub.db")
    migrate_to_head(database_url)
    settings = build_settings(
        database_url,
        demo_mode=demo_mode,
        seed_demo_data=seed_demo_data,
    )
    return create_app(settings_override=settings)


def build_client(
    tmp_path: Path,
    *,
    demo_mode: bool = True,
    seed_demo_data: bool | None = None,
):
    app = build_app(tmp_path, demo_mode=demo_mode, seed_demo_data=seed_demo_data)
    return app, TestClient(app)


def login_as(
    client: TestClient,
    email: str,
    *,
    password: str = DEMO_PASSWORD,
    next_path: str = "/",
):
    response = client.post(
        "/login",
        json={
            "email": email,
            "password": password,
            "next_path": next_path,
        },
    )
    assert response.status_code == 200, response.text
    return response


def logout(client: TestClient):
    response = client.post("/logout", follow_redirects=False)
    assert response.status_code == 303, response.text
    return response


def switch_demo_user(
    client: TestClient,
    email: str,
    *,
    next_path: str = "/",
):
    response = client.get(
        "/switch-user",
        params={"email": email, "next": next_path},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return response
