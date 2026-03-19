"""Scope locations to organisations and make job locations canonical.

Revision ID: 20260319_0004
Revises: 20260319_0003
Create Date: 2026-03-19 15:30:00
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session


revision: str = "20260319_0004"
down_revision: str | None = "20260319_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


users_table = sa.table(
    "users",
    sa.column("id", sa.Uuid()),
    sa.column("organisation_id", sa.Uuid()),
)

locations_table = sa.table(
    "locations",
    sa.column("id", sa.Uuid()),
    sa.column("user_id", sa.Uuid()),
    sa.column("organisation_id", sa.Uuid()),
    sa.column("name", sa.Text()),
    sa.column("created_at", sa.DateTime(timezone=True)),
)

assets_table = sa.table(
    "assets",
    sa.column("id", sa.Uuid()),
    sa.column("location_id", sa.Uuid()),
    sa.column("name", sa.Text()),
    sa.column("created_at", sa.DateTime(timezone=True)),
)

jobs_table = sa.table(
    "jobs",
    sa.column("id", sa.Uuid()),
    sa.column("created_by", sa.Uuid()),
    sa.column("location", sa.Text()),
    sa.column("location_snapshot", sa.Text()),
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


def _canonical_location_id(
    session: Session,
    *,
    canonical_locations: dict[tuple[uuid.UUID, str], uuid.UUID],
    organisation_id: uuid.UUID,
    name: str,
    now: datetime,
) -> uuid.UUID:
    key = (organisation_id, name)
    location_id = canonical_locations.get(key)
    if location_id is None:
        location_id = uuid.uuid4()
        canonical_locations[key] = location_id
        session.execute(
            sa.insert(locations_table).values(
                id=location_id,
                organisation_id=organisation_id,
                name=name,
                created_at=now,
            )
        )
    return location_id


def upgrade() -> None:
    with op.batch_alter_table("locations", recreate="auto") as batch_op:
        batch_op.add_column(sa.Column("organisation_id", sa.Uuid(), nullable=True))

    with op.batch_alter_table("jobs", recreate="auto") as batch_op:
        batch_op.add_column(sa.Column("location_snapshot", sa.Text(), nullable=True))

    bind = op.get_bind()
    session = Session(bind=bind)
    now = datetime.now(timezone.utc)

    session.execute(sa.update(jobs_table).values(location_snapshot=jobs_table.c.location))

    user_org_ids = {
        user_id: organisation_id
        for user_id, organisation_id in session.execute(
            sa.select(users_table.c.id, users_table.c.organisation_id)
        ).all()
    }

    canonical_locations: dict[tuple[uuid.UUID, str], uuid.UUID] = {}
    location_id_map: dict[uuid.UUID, uuid.UUID] = {}
    duplicate_location_ids: list[uuid.UUID] = []

    location_rows = session.execute(
        sa.select(
            locations_table.c.id,
            locations_table.c.user_id,
            locations_table.c.name,
            locations_table.c.created_at,
        ).order_by(locations_table.c.created_at.asc(), locations_table.c.id.asc())
    ).all()

    for location_id, user_id, name, _created_at in location_rows:
        organisation_id = user_org_ids.get(user_id)
        if organisation_id is None:
            raise RuntimeError(f"Cannot migrate location {location_id}: user {user_id} has no organisation")

        key = (organisation_id, name)
        canonical_id = canonical_locations.get(key)
        if canonical_id is None:
            canonical_id = location_id
            canonical_locations[key] = canonical_id
            session.execute(
                sa.update(locations_table)
                .where(locations_table.c.id == location_id)
                .values(organisation_id=organisation_id)
            )
        else:
            duplicate_location_ids.append(location_id)
        location_id_map[location_id] = canonical_id

    job_rows = session.execute(
        sa.select(
            jobs_table.c.id,
            jobs_table.c.created_by,
            jobs_table.c.location_snapshot,
        ).order_by(jobs_table.c.id.asc())
    ).all()

    for job_id, created_by, location_snapshot in job_rows:
        organisation_id = user_org_ids.get(created_by)
        if organisation_id is None:
            raise RuntimeError(f"Cannot migrate job {job_id}: creator {created_by} has no organisation")
        if not location_snapshot:
            raise RuntimeError(f"Cannot migrate job {job_id}: missing location snapshot")

        canonical_id = _canonical_location_id(
            session,
            canonical_locations=canonical_locations,
            organisation_id=organisation_id,
            name=location_snapshot,
            now=now,
        )
        session.execute(
            sa.update(jobs_table)
            .where(jobs_table.c.id == job_id)
            .values(location_id=canonical_id)
        )

    canonical_assets: dict[tuple[uuid.UUID, str], uuid.UUID] = {}
    duplicate_asset_ids: list[uuid.UUID] = []
    asset_id_map: dict[uuid.UUID, uuid.UUID] = {}

    asset_rows = session.execute(
        sa.select(
            assets_table.c.id,
            assets_table.c.location_id,
            assets_table.c.name,
            assets_table.c.created_at,
        ).order_by(assets_table.c.created_at.asc(), assets_table.c.id.asc())
    ).all()

    for asset_id, location_id, name, _created_at in asset_rows:
        canonical_location_id = location_id_map.get(location_id, location_id)
        key = (canonical_location_id, name)
        canonical_asset_id = canonical_assets.get(key)
        if canonical_asset_id is None:
            canonical_asset_id = asset_id
            canonical_assets[key] = canonical_asset_id
            if location_id != canonical_location_id:
                session.execute(
                    sa.update(assets_table)
                    .where(assets_table.c.id == asset_id)
                    .values(location_id=canonical_location_id)
                )
        else:
            duplicate_asset_ids.append(asset_id)
        asset_id_map[asset_id] = canonical_asset_id

    for duplicate_asset_id in duplicate_asset_ids:
        canonical_asset_id = asset_id_map[duplicate_asset_id]
        session.execute(
            sa.update(jobs_table)
            .where(jobs_table.c.asset_id == duplicate_asset_id)
            .values(asset_id=canonical_asset_id)
        )
        session.execute(
            sa.update(events_table)
            .where(events_table.c.asset_id == duplicate_asset_id)
            .values(asset_id=canonical_asset_id)
        )

    session.execute(
        sa.update(events_table).values(
            location_id=sa.select(jobs_table.c.location_id)
            .where(jobs_table.c.id == events_table.c.job_id)
            .scalar_subquery()
        )
    )
    session.execute(
        sa.update(events_table).values(
            asset_id=sa.select(jobs_table.c.asset_id)
            .where(jobs_table.c.id == events_table.c.job_id)
            .scalar_subquery()
        )
    )

    if duplicate_asset_ids:
        session.execute(sa.delete(assets_table).where(assets_table.c.id.in_(duplicate_asset_ids)))
    if duplicate_location_ids:
        session.execute(sa.delete(locations_table).where(locations_table.c.id.in_(duplicate_location_ids)))

    session.commit()

    with op.batch_alter_table("jobs", recreate="auto") as batch_op:
        batch_op.alter_column("location_snapshot", existing_type=sa.Text(), nullable=False)
        batch_op.alter_column("location_id", existing_type=sa.Uuid(), nullable=False)
        batch_op.drop_column("location")

    with op.batch_alter_table("locations", recreate="auto") as batch_op:
        batch_op.drop_index("ix_locations_user_id_name")
        batch_op.drop_index("ix_locations_user_id")
        batch_op.drop_constraint("uq_locations_user_name", type_="unique")
        batch_op.create_foreign_key(
            "fk_locations_organisation_id_organisations",
            "organisations",
            ["organisation_id"],
            ["id"],
        )
        batch_op.alter_column("organisation_id", existing_type=sa.Uuid(), nullable=False)
        batch_op.create_unique_constraint("uq_locations_organisation_name", ["organisation_id", "name"])
        batch_op.create_index("ix_locations_organisation_id", ["organisation_id"])
        batch_op.create_index("ix_locations_organisation_id_name", ["organisation_id", "name"])
        batch_op.drop_column("user_id")


def downgrade() -> None:
    with op.batch_alter_table("locations", recreate="auto") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Uuid(), nullable=True))

    with op.batch_alter_table("jobs", recreate="auto") as batch_op:
        batch_op.add_column(sa.Column("location", sa.Text(), nullable=True))

    bind = op.get_bind()
    session = Session(bind=bind)

    session.execute(sa.update(jobs_table).values(location=jobs_table.c.location_snapshot))

    organisation_user_ids: dict[uuid.UUID, uuid.UUID] = {}
    user_rows = session.execute(
        sa.select(users_table.c.id, users_table.c.organisation_id).order_by(users_table.c.id.asc())
    ).all()
    for user_id, organisation_id in user_rows:
        if organisation_id is not None and organisation_id not in organisation_user_ids:
            organisation_user_ids[organisation_id] = user_id

    location_rows = session.execute(
        sa.select(locations_table.c.id, locations_table.c.organisation_id).order_by(locations_table.c.id.asc())
    ).all()
    for location_id, organisation_id in location_rows:
        user_id = organisation_user_ids.get(organisation_id)
        if user_id is None:
            raise RuntimeError(
                f"Cannot downgrade location {location_id}: organisation {organisation_id} has no user to own it"
            )
        session.execute(
            sa.update(locations_table)
            .where(locations_table.c.id == location_id)
            .values(user_id=user_id)
        )

    session.commit()

    with op.batch_alter_table("jobs", recreate="auto") as batch_op:
        batch_op.alter_column("location_id", existing_type=sa.Uuid(), nullable=True)
        batch_op.alter_column("location", existing_type=sa.Text(), nullable=False)
        batch_op.drop_column("location_snapshot")

    with op.batch_alter_table("locations", recreate="auto") as batch_op:
        batch_op.drop_index("ix_locations_organisation_id_name")
        batch_op.drop_index("ix_locations_organisation_id")
        batch_op.drop_constraint("uq_locations_organisation_name", type_="unique")
        batch_op.drop_constraint("fk_locations_organisation_id_organisations", type_="foreignkey")
        batch_op.create_unique_constraint("uq_locations_user_name", ["user_id", "name"])
        batch_op.create_index("ix_locations_user_id", ["user_id"])
        batch_op.create_index("ix_locations_user_id_name", ["user_id", "name"])
        batch_op.alter_column("user_id", existing_type=sa.Uuid(), nullable=False)
        batch_op.drop_column("organisation_id")
