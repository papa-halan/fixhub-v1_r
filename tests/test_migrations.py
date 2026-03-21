from __future__ import annotations

from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect

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

    assert list(script.get_heads()) == ["20260321_0007"]


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
