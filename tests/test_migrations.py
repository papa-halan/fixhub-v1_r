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

    assert list(script.get_heads()) == ["20260404_0011"]


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


def test_event_target_status_migration_backfills_deterministic_values_only(tmp_path) -> None:
    database_url = sqlite_database_url(tmp_path / "event-target-status.db")
    config = alembic_config(database_url)
    command.upgrade(config, "20260321_0008")

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
    users = sa.Table(
        "users",
        metadata,
        sa.Column("id", sa.Uuid()),
        sa.Column("name", sa.Text()),
        sa.Column("email", sa.Text()),
        sa.Column("role", sa.Text()),
        sa.Column("organisation_id", sa.Uuid()),
        sa.Column("is_demo_account", sa.Boolean()),
        sa.Column("password_hash", sa.Text()),
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
    jobs = sa.Table(
        "jobs",
        metadata,
        sa.Column("id", sa.Uuid()),
        sa.Column("title", sa.Text()),
        sa.Column("description", sa.Text()),
        sa.Column("location", sa.Text()),
        sa.Column("status", sa.Text()),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("assigned_org_id", sa.Uuid()),
        sa.Column("assigned_contractor_user_id", sa.Uuid()),
        sa.Column("organisation_id", sa.Uuid()),
        sa.Column("location_id", sa.Uuid()),
        sa.Column("location_detail_text", sa.Text()),
        sa.Column("asset_id", sa.Uuid()),
        sa.Column("asset_name", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    events = sa.Table(
        "events",
        metadata,
        sa.Column("id", sa.Uuid()),
        sa.Column("job_id", sa.Uuid()),
        sa.Column("actor_user_id", sa.Uuid()),
        sa.Column("actor_org_id", sa.Uuid()),
        sa.Column("location_id", sa.Uuid()),
        sa.Column("asset_id", sa.Uuid()),
        sa.Column("event_type", sa.Text()),
        sa.Column("message", sa.Text()),
        sa.Column("reason_code", sa.Text()),
        sa.Column("responsibility_stage", sa.Text()),
        sa.Column("owner_scope", sa.Text()),
        sa.Column("responsibility_owner", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )

    organisation_id = uuid.uuid4()
    user_id = uuid.uuid4()
    location_id = uuid.uuid4()
    job_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    event_ids = {
        "report_created": uuid.uuid4(),
        "status_change_triaged": uuid.uuid4(),
        "status_change_unknown": uuid.uuid4(),
        "schedule": uuid.uuid4(),
        "assignment": uuid.uuid4(),
        "note": uuid.uuid4(),
    }

    with engine.begin() as connection:
        connection.execute(
            sa.insert(organisations).values(
                id=organisation_id,
                name="Backfill Test Org",
                type="university",
                created_at=now,
            )
        )
        connection.execute(
            sa.insert(users).values(
                id=user_id,
                name="Backfill User",
                email="backfill@example.com",
                role="admin",
                organisation_id=organisation_id,
                is_demo_account=False,
                password_hash="scrypt$placeholder",
                created_at=now,
            )
        )
        connection.execute(
            sa.insert(locations).values(
                id=location_id,
                organisation_id=organisation_id,
                parent_id=None,
                name="Block A",
                type="building",
                created_at=now,
            )
        )
        connection.execute(
            sa.insert(jobs).values(
                id=job_id,
                title="Leaking tap",
                description="Water under sink",
                location="Block A",
                status="new",
                created_by=user_id,
                assigned_org_id=None,
                assigned_contractor_user_id=None,
                organisation_id=organisation_id,
                location_id=location_id,
                location_detail_text=None,
                asset_id=None,
                asset_name=None,
                created_at=now,
                updated_at=now,
            )
        )
        connection.execute(
            sa.insert(events),
            [
                {
                    "id": event_ids["report_created"],
                    "job_id": job_id,
                    "actor_user_id": user_id,
                    "actor_org_id": organisation_id,
                    "location_id": location_id,
                    "asset_id": None,
                    "event_type": "report_created",
                    "message": "Report created",
                    "reason_code": None,
                    "responsibility_stage": "reception",
                    "owner_scope": "organisation",
                    "responsibility_owner": "coordinator",
                    "created_at": now,
                },
                {
                    "id": event_ids["status_change_triaged"],
                    "job_id": job_id,
                    "actor_user_id": user_id,
                    "actor_org_id": organisation_id,
                    "location_id": location_id,
                    "asset_id": None,
                    "event_type": "status_change",
                    "message": "Marked job triaged",
                    "reason_code": None,
                    "responsibility_stage": "triage",
                    "owner_scope": "organisation",
                    "responsibility_owner": "triage_officer",
                    "created_at": now,
                },
                {
                    "id": event_ids["status_change_unknown"],
                    "job_id": job_id,
                    "actor_user_id": user_id,
                    "actor_org_id": organisation_id,
                    "location_id": location_id,
                    "asset_id": None,
                    "event_type": "status_change",
                    "message": "Unknown legacy status change",
                    "reason_code": None,
                    "responsibility_stage": "triage",
                    "owner_scope": "organisation",
                    "responsibility_owner": "triage_officer",
                    "created_at": now,
                },
                {
                    "id": event_ids["schedule"],
                    "job_id": job_id,
                    "actor_user_id": user_id,
                    "actor_org_id": organisation_id,
                    "location_id": location_id,
                    "asset_id": None,
                    "event_type": "schedule",
                    "message": "Scheduled site visit",
                    "reason_code": None,
                    "responsibility_stage": "coordination",
                    "owner_scope": "organisation",
                    "responsibility_owner": "coordinator",
                    "created_at": now,
                },
                {
                    "id": event_ids["assignment"],
                    "job_id": job_id,
                    "actor_user_id": user_id,
                    "actor_org_id": organisation_id,
                    "location_id": location_id,
                    "asset_id": None,
                    "event_type": "assignment",
                    "message": "Assigned contractor",
                    "reason_code": None,
                    "responsibility_stage": "triage",
                    "owner_scope": "organisation",
                    "responsibility_owner": "coordinator",
                    "created_at": now,
                },
                {
                    "id": event_ids["note"],
                    "job_id": job_id,
                    "actor_user_id": user_id,
                    "actor_org_id": organisation_id,
                    "location_id": location_id,
                    "asset_id": None,
                    "event_type": "note",
                    "message": "Manual note",
                    "reason_code": None,
                    "responsibility_stage": "coordination",
                    "owner_scope": "organisation",
                    "responsibility_owner": "coordinator",
                    "created_at": now,
                },
            ],
        )

    command.upgrade(config, "head")

    migrated_events = sa.Table(
        "events",
        sa.MetaData(),
        sa.Column("id", sa.Uuid()),
        sa.Column("target_status", sa.Text()),
    )

    with engine.connect() as connection:
        target_status_by_id = dict(
            connection.execute(
                sa.select(migrated_events.c.id, migrated_events.c.target_status)
            ).all()
        )

    assert target_status_by_id[event_ids["report_created"]] == "new"
    assert target_status_by_id[event_ids["status_change_triaged"]] == "triaged"
    assert target_status_by_id[event_ids["status_change_unknown"]] is None
    assert target_status_by_id[event_ids["schedule"]] == "scheduled"
    assert target_status_by_id[event_ids["assignment"]] is None
    assert target_status_by_id[event_ids["note"]] is None
    assert len(ScriptDirectory.from_config(config).get_heads()) == 1


def test_direct_dispatch_migration_backfills_org_context_for_named_contractors(tmp_path) -> None:
    database_url = sqlite_database_url(tmp_path / "direct-dispatch-org-context.db")
    config = alembic_config(database_url)
    command.upgrade(config, "20260404_0009")

    engine = create_engine(database_url, future=True)
    metadata = sa.MetaData()
    organisations = sa.Table(
        "organisations",
        metadata,
        sa.Column("id", sa.Uuid()),
        sa.Column("name", sa.Text()),
        sa.Column("type", sa.Text()),
        sa.Column("contractor_mode", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    users = sa.Table(
        "users",
        metadata,
        sa.Column("id", sa.Uuid()),
        sa.Column("name", sa.Text()),
        sa.Column("email", sa.Text()),
        sa.Column("role", sa.Text()),
        sa.Column("organisation_id", sa.Uuid()),
        sa.Column("is_demo_account", sa.Boolean()),
        sa.Column("password_hash", sa.Text()),
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
    jobs = sa.Table(
        "jobs",
        metadata,
        sa.Column("id", sa.Uuid()),
        sa.Column("title", sa.Text()),
        sa.Column("description", sa.Text()),
        sa.Column("location_snapshot", sa.Text()),
        sa.Column("status", sa.Text()),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("assigned_org_id", sa.Uuid()),
        sa.Column("assigned_contractor_user_id", sa.Uuid()),
        sa.Column("organisation_id", sa.Uuid()),
        sa.Column("location_id", sa.Uuid()),
        sa.Column("location_detail_text", sa.Text()),
        sa.Column("asset_id", sa.Uuid()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    tenant_org_id = uuid.uuid4()
    contractor_org_id = uuid.uuid4()
    resident_user_id = uuid.uuid4()
    contractor_user_id = uuid.uuid4()
    location_id = uuid.uuid4()
    job_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    with engine.begin() as connection:
        connection.execute(
            sa.insert(organisations),
            [
                {
                    "id": tenant_org_id,
                    "name": "Student Living",
                    "type": "university",
                    "contractor_mode": None,
                    "created_at": now,
                },
                {
                    "id": contractor_org_id,
                    "name": "Newcastle Plumbing",
                    "type": "contractor",
                    "contractor_mode": "external_contractor",
                    "created_at": now,
                },
            ],
        )
        connection.execute(
            sa.insert(users),
            [
                {
                    "id": resident_user_id,
                    "name": "Resident Reporter",
                    "email": "resident@example.com",
                    "role": "resident",
                    "organisation_id": tenant_org_id,
                    "is_demo_account": False,
                    "password_hash": "scrypt$placeholder",
                    "created_at": now,
                },
                {
                    "id": contractor_user_id,
                    "name": "Named Contractor",
                    "email": "named.contractor@example.com",
                    "role": "contractor",
                    "organisation_id": contractor_org_id,
                    "is_demo_account": False,
                    "password_hash": "scrypt$placeholder",
                    "created_at": now,
                },
            ],
        )
        connection.execute(
            sa.insert(locations).values(
                id=location_id,
                organisation_id=tenant_org_id,
                parent_id=None,
                name="Block A Room 14",
                type="unit",
                created_at=now,
            )
        )
        connection.execute(
            sa.insert(jobs).values(
                id=job_id,
                title="Leaking tap",
                description="Water under sink",
                location_snapshot="Block A Room 14",
                status="assigned",
                created_by=resident_user_id,
                assigned_org_id=None,
                assigned_contractor_user_id=contractor_user_id,
                organisation_id=tenant_org_id,
                location_id=location_id,
                location_detail_text=None,
                asset_id=None,
                created_at=now,
                updated_at=now,
            )
        )

    command.upgrade(config, "head")

    migrated_jobs = sa.Table(
        "jobs",
        sa.MetaData(),
        sa.Column("id", sa.Uuid()),
        sa.Column("assigned_org_id", sa.Uuid()),
        sa.Column("assigned_contractor_user_id", sa.Uuid()),
    )

    with engine.connect() as connection:
        assigned_org_id, assigned_contractor_user_id = connection.execute(
            sa.select(
                migrated_jobs.c.assigned_org_id,
                migrated_jobs.c.assigned_contractor_user_id,
            ).where(migrated_jobs.c.id == job_id)
        ).one()

    assert assigned_org_id == contractor_org_id
    assert assigned_contractor_user_id == contractor_user_id
