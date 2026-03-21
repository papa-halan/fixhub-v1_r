from __future__ import annotations

from datetime import datetime, timezone
import uuid

from alembic import command
from alembic.script import ScriptDirectory
import sqlalchemy as sa
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

    assert list(script.get_heads()) == ["20260321_0008"]


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
