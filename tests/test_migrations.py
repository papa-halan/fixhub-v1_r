from __future__ import annotations

from datetime import datetime, timezone
import uuid

from alembic import command
from alembic.script import ScriptDirectory
import sqlalchemy as sa
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import make_url

from app.core.config import ROOT_DIR
from app.core.database import (
    build_engine,
    database_connection_error_message,
    describe_database_target,
    prepare_database_url,
    resolve_database_url,
)
from tests.support import alembic_config, downgrade_to_base, migrate_to_head, sqlite_database_url


EXPECTED_TABLES = {
    "alembic_version",
    "assets",
    "events",
    "jobs",
    "locations",
    "organisations",
    "users",
}


def test_alembic_has_a_single_head() -> None:
    config = alembic_config("sqlite+pysqlite:///./fixhub.db")
    script = ScriptDirectory.from_config(config)

    assert list(script.get_heads()) == ["20260321_0008"]


def test_demo_mode_without_database_url_uses_local_sqlite_database(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("FIXHUB_DEMO_MODE", "1")

    resolved_url = resolve_database_url()
    target = describe_database_target(resolved_url)

    assert resolved_url == f"sqlite:///{(ROOT_DIR / 'fixhub.db').as_posix()}"
    assert target.dialect == "sqlite"
    assert target.host == "local"
    assert target.port == "-"
    assert target.database == (ROOT_DIR / "fixhub.db").as_posix()


def test_build_engine_adds_default_postgres_connect_timeout_when_missing(monkeypatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@db:5432/fixhub?sslmode=require",
    )

    engine = build_engine()
    try:
        assert engine.url.get_backend_name() == "postgresql"
        assert engine.url.query["connect_timeout"] == "5"
        assert engine.url.query["sslmode"] == "require"
    finally:
        engine.dispose()


def test_prepare_database_url_preserves_existing_postgres_connect_timeout() -> None:
    prepared_url = prepare_database_url(
        "postgresql+psycopg://postgres:postgres@db:5432/fixhub?connect_timeout=2&sslmode=require"
    )
    parsed_url = make_url(prepared_url)

    assert parsed_url.query["connect_timeout"] == "2"
    assert parsed_url.query["sslmode"] == "require"


def test_database_connection_error_message_is_actionable_for_demo_mode() -> None:
    message = database_connection_error_message(
        "postgresql+psycopg://postgres:postgres@db:5432/fixhub",
        demo_mode=True,
    )

    assert "host=db" in message
    assert "port=5432" in message
    assert "database=fixhub" in message
    assert "demo_mode=True" in message
    assert "unset DATABASE_URL" in message
    assert "rerun the Alembic command" in message


def test_migrations_upgrade_downgrade_round_trip_and_model_check_are_clean(tmp_path) -> None:
    database_url = sqlite_database_url(tmp_path / "migrations.db")

    migrate_to_head(database_url)
    engine = create_engine(database_url, future=True)
    assert set(inspect(engine).get_table_names()) == EXPECTED_TABLES
    command.check(alembic_config(database_url))

    downgrade_to_base(database_url)
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}

    migrate_to_head(database_url)
    assert set(inspect(engine).get_table_names()) == EXPECTED_TABLES


def test_explicit_alembic_config_url_beats_ambient_database_url(tmp_path, monkeypatch) -> None:
    target_url = sqlite_database_url(tmp_path / "target.db")
    ambient_url = sqlite_database_url(tmp_path / "ambient.db")
    monkeypatch.setenv("DATABASE_URL", ambient_url)

    migrate_to_head(target_url)

    target_engine = create_engine(target_url, future=True)
    ambient_engine = create_engine(ambient_url, future=True)

    assert set(inspect(target_engine).get_table_names()) == EXPECTED_TABLES
    assert inspect(ambient_engine).get_table_names() == []


def test_location_cleanup_migration_removes_unreferenced_legacy_placeholders(tmp_path) -> None:
    database_url = sqlite_database_url(tmp_path / "cleanup.db")
    config = alembic_config(database_url)
    command.upgrade(config, "20260321_0007")

    engine = create_engine(database_url, future=True)
    metadata = sa.MetaData()
    organisations = sa.Table(
        "organisations",
        metadata,
        sa.Column("id", sa.Uuid()),
        sa.Column("name", sa.Text()),
        sa.Column("type", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    locations = sa.Table(
        "locations",
        metadata,
        sa.Column("id", sa.Uuid()),
        sa.Column("organisation_id", sa.Uuid()),
        sa.Column("parent_id", sa.Uuid()),
        sa.Column("name", sa.Text()),
        sa.Column("type", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )

    organisation_id = uuid.uuid4()
    placeholder_location_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    with engine.begin() as connection:
        connection.execute(
            sa.insert(organisations).values(
                id=organisation_id,
                name="Cleanup Test Org",
                type="university",
                created_at=now,
            )
        )
        connection.execute(
            sa.insert(locations).values(
                id=placeholder_location_id,
                organisation_id=organisation_id,
                parent_id=None,
                name="a",
                type="space",
                created_at=now,
            )
        )

    command.upgrade(config, "head")

    with engine.connect() as connection:
        remaining_names = set(connection.execute(sa.select(locations.c.name)).scalars())

    assert "a" not in remaining_names
