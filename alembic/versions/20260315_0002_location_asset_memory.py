"""Add persistent location and asset catalog tables.

Revision ID: 20260315_0002
Revises: 20260313_0001
Create Date: 2026-03-15 18:40:00
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session


revision: str = "20260315_0002"
down_revision: str | None = "20260313_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


locations_table = sa.table(
    "locations",
    sa.column("id", sa.Uuid()),
    sa.column("user_id", sa.Uuid()),
    sa.column("name", sa.Text()),
    sa.column("created_at", sa.DateTime(timezone=True)),
)

jobs_table = sa.table(
    "jobs",
    sa.column("id", sa.Uuid()),
    sa.column("created_by", sa.Uuid()),
    sa.column("location", sa.Text()),
    sa.column("location_id", sa.Uuid()),
    sa.column("asset_id", sa.Uuid()),
)

events_table = sa.table(
    "events",
    sa.column("id", sa.Uuid()),
    sa.column("job_id", sa.Uuid()),
    sa.column("location_id", sa.Uuid()),
    sa.column("asset_id", sa.Uuid()),
)


def has_table(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def has_column(inspector, table_name: str, column_name: str) -> bool:
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def has_index(inspector, table_name: str, index_name: str) -> bool:
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def has_foreign_key(inspector, table_name: str, fk_name: str) -> bool:
    return fk_name in {foreign_key.get("name") for foreign_key in inspector.get_foreign_keys(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not has_table(inspector, "locations"):
        op.create_table(
            "locations",
            sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("name", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.UniqueConstraint("user_id", "name", name="uq_locations_user_name"),
        )
        inspector = sa.inspect(bind)
    if not has_index(inspector, "locations", "ix_locations_user_id"):
        op.create_index("ix_locations_user_id", "locations", ["user_id"])
    if not has_index(inspector, "locations", "ix_locations_user_id_name"):
        op.create_index("ix_locations_user_id_name", "locations", ["user_id", "name"])

    inspector = sa.inspect(bind)
    if not has_table(inspector, "assets"):
        op.create_table(
            "assets",
            sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
            sa.Column("location_id", sa.Uuid(), nullable=False),
            sa.Column("name", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
            sa.UniqueConstraint("location_id", "name", name="uq_assets_location_name"),
        )
        inspector = sa.inspect(bind)
    if not has_index(inspector, "assets", "ix_assets_location_id"):
        op.create_index("ix_assets_location_id", "assets", ["location_id"])
    if not has_index(inspector, "assets", "ix_assets_location_id_name"):
        op.create_index("ix_assets_location_id_name", "assets", ["location_id", "name"])

    inspector = sa.inspect(bind)
    jobs_has_location_id = has_column(inspector, "jobs", "location_id")
    jobs_has_asset_id = has_column(inspector, "jobs", "asset_id")
    jobs_has_location_fk = has_foreign_key(inspector, "jobs", "fk_jobs_location_id_locations")
    jobs_has_asset_fk = has_foreign_key(inspector, "jobs", "fk_jobs_asset_id_assets")
    jobs_has_location_index = has_index(inspector, "jobs", "ix_jobs_location_id")
    jobs_has_asset_index = has_index(inspector, "jobs", "ix_jobs_asset_id")
    jobs_has_pair_index = has_index(inspector, "jobs", "ix_jobs_location_asset")

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("jobs", recreate="auto") as batch_op:
            if not jobs_has_location_id:
                batch_op.add_column(sa.Column("location_id", sa.Uuid(), nullable=True))
            if not jobs_has_asset_id:
                batch_op.add_column(sa.Column("asset_id", sa.Uuid(), nullable=True))
            if not jobs_has_location_fk:
                batch_op.create_foreign_key(
                    "fk_jobs_location_id_locations",
                    "locations",
                    ["location_id"],
                    ["id"],
                )
            if not jobs_has_asset_fk:
                batch_op.create_foreign_key(
                    "fk_jobs_asset_id_assets",
                    "assets",
                    ["asset_id"],
                    ["id"],
                )
            if not jobs_has_location_index:
                batch_op.create_index("ix_jobs_location_id", ["location_id"])
            if not jobs_has_asset_index:
                batch_op.create_index("ix_jobs_asset_id", ["asset_id"])
            if not jobs_has_pair_index:
                batch_op.create_index("ix_jobs_location_asset", ["location_id", "asset_id"])
    else:
        if not jobs_has_location_id:
            op.add_column("jobs", sa.Column("location_id", sa.Uuid(), nullable=True))
        if not jobs_has_asset_id:
            op.add_column("jobs", sa.Column("asset_id", sa.Uuid(), nullable=True))
        if not jobs_has_location_fk:
            op.create_foreign_key("fk_jobs_location_id_locations", "jobs", "locations", ["location_id"], ["id"])
        if not jobs_has_asset_fk:
            op.create_foreign_key("fk_jobs_asset_id_assets", "jobs", "assets", ["asset_id"], ["id"])
        if not jobs_has_location_index:
            op.create_index("ix_jobs_location_id", "jobs", ["location_id"])
        if not jobs_has_asset_index:
            op.create_index("ix_jobs_asset_id", "jobs", ["asset_id"])
        if not jobs_has_pair_index:
            op.create_index("ix_jobs_location_asset", "jobs", ["location_id", "asset_id"])

    inspector = sa.inspect(bind)
    events_has_location_id = has_column(inspector, "events", "location_id")
    events_has_asset_id = has_column(inspector, "events", "asset_id")
    events_has_location_fk = has_foreign_key(inspector, "events", "fk_events_location_id_locations")
    events_has_asset_fk = has_foreign_key(inspector, "events", "fk_events_asset_id_assets")
    events_has_location_index = has_index(inspector, "events", "ix_events_location_id")
    events_has_asset_index = has_index(inspector, "events", "ix_events_asset_id")
    events_has_pair_index = has_index(inspector, "events", "ix_events_location_asset_created_at")

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("events", recreate="auto") as batch_op:
            if not events_has_location_id:
                batch_op.add_column(sa.Column("location_id", sa.Uuid(), nullable=True))
            if not events_has_asset_id:
                batch_op.add_column(sa.Column("asset_id", sa.Uuid(), nullable=True))
            if not events_has_location_fk:
                batch_op.create_foreign_key(
                    "fk_events_location_id_locations",
                    "locations",
                    ["location_id"],
                    ["id"],
                )
            if not events_has_asset_fk:
                batch_op.create_foreign_key(
                    "fk_events_asset_id_assets",
                    "assets",
                    ["asset_id"],
                    ["id"],
                )
            if not events_has_location_index:
                batch_op.create_index("ix_events_location_id", ["location_id"])
            if not events_has_asset_index:
                batch_op.create_index("ix_events_asset_id", ["asset_id"])
            if not events_has_pair_index:
                batch_op.create_index(
                    "ix_events_location_asset_created_at",
                    ["location_id", "asset_id", "created_at"],
                )
    else:
        if not events_has_location_id:
            op.add_column("events", sa.Column("location_id", sa.Uuid(), nullable=True))
        if not events_has_asset_id:
            op.add_column("events", sa.Column("asset_id", sa.Uuid(), nullable=True))
        if not events_has_location_fk:
            op.create_foreign_key("fk_events_location_id_locations", "events", "locations", ["location_id"], ["id"])
        if not events_has_asset_fk:
            op.create_foreign_key("fk_events_asset_id_assets", "events", "assets", ["asset_id"], ["id"])
        if not events_has_location_index:
            op.create_index("ix_events_location_id", "events", ["location_id"])
        if not events_has_asset_index:
            op.create_index("ix_events_asset_id", "events", ["asset_id"])
        if not events_has_pair_index:
            op.create_index(
                "ix_events_location_asset_created_at",
                "events",
                ["location_id", "asset_id", "created_at"],
            )

    session = Session(bind=bind)
    now = datetime.now(timezone.utc)
    location_ids: dict[tuple[uuid.UUID, str], uuid.UUID] = {}

    job_rows = session.execute(
        sa.select(jobs_table.c.id, jobs_table.c.created_by, jobs_table.c.location)
        .order_by(jobs_table.c.created_by, jobs_table.c.location, jobs_table.c.id)
    ).all()

    for job_id, created_by, location_name in job_rows:
        if created_by is None or not location_name:
            continue
        key = (created_by, location_name)
        location_id = location_ids.get(key)
        if location_id is None:
            location_id = session.execute(
                sa.select(locations_table.c.id)
                .where(
                    locations_table.c.user_id == created_by,
                    locations_table.c.name == location_name,
                )
                .limit(1)
            ).scalar_one_or_none()
        if location_id is None:
            location_id = uuid.uuid4()
            session.execute(
                sa.insert(locations_table).values(
                    id=location_id,
                    user_id=created_by,
                    name=location_name,
                    created_at=now,
                )
            )
        location_ids[key] = location_id
        session.execute(
            sa.update(jobs_table)
            .where(jobs_table.c.id == job_id)
            .values(location_id=location_id)
        )

    session.execute(
        sa.update(events_table)
        .values(
            location_id=sa.select(jobs_table.c.location_id)
            .where(jobs_table.c.id == events_table.c.job_id)
            .scalar_subquery()
        )
    )
    session.execute(
        sa.update(events_table)
        .values(
            asset_id=sa.select(jobs_table.c.asset_id)
            .where(jobs_table.c.id == events_table.c.job_id)
            .scalar_subquery()
        )
    )
    session.commit()


def downgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("events", recreate="auto") as batch_op:
            batch_op.drop_index("ix_events_location_asset_created_at")
            batch_op.drop_index("ix_events_asset_id")
            batch_op.drop_index("ix_events_location_id")
            batch_op.drop_constraint("fk_events_asset_id_assets", type_="foreignkey")
            batch_op.drop_constraint("fk_events_location_id_locations", type_="foreignkey")
            batch_op.drop_column("asset_id")
            batch_op.drop_column("location_id")

        with op.batch_alter_table("jobs", recreate="auto") as batch_op:
            batch_op.drop_index("ix_jobs_location_asset")
            batch_op.drop_index("ix_jobs_asset_id")
            batch_op.drop_index("ix_jobs_location_id")
            batch_op.drop_constraint("fk_jobs_asset_id_assets", type_="foreignkey")
            batch_op.drop_constraint("fk_jobs_location_id_locations", type_="foreignkey")
            batch_op.drop_column("asset_id")
            batch_op.drop_column("location_id")
    else:
        op.drop_index("ix_events_location_asset_created_at", table_name="events")
        op.drop_index("ix_events_asset_id", table_name="events")
        op.drop_index("ix_events_location_id", table_name="events")
        op.drop_constraint("fk_events_asset_id_assets", "events", type_="foreignkey")
        op.drop_constraint("fk_events_location_id_locations", "events", type_="foreignkey")
        op.drop_column("events", "asset_id")
        op.drop_column("events", "location_id")

        op.drop_index("ix_jobs_location_asset", table_name="jobs")
        op.drop_index("ix_jobs_asset_id", table_name="jobs")
        op.drop_index("ix_jobs_location_id", table_name="jobs")
        op.drop_constraint("fk_jobs_asset_id_assets", "jobs", type_="foreignkey")
        op.drop_constraint("fk_jobs_location_id_locations", "jobs", type_="foreignkey")
        op.drop_column("jobs", "asset_id")
        op.drop_column("jobs", "location_id")

    op.drop_index("ix_assets_location_id_name", table_name="assets")
    op.drop_index("ix_assets_location_id", table_name="assets")
    op.drop_table("assets")

    op.drop_index("ix_locations_user_id_name", table_name="locations")
    op.drop_index("ix_locations_user_id", table_name="locations")
    op.drop_table("locations")
