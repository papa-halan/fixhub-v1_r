"""Freeze event display labels as historical snapshots.

Revision ID: 20260404_0013
Revises: 20260404_0012
Create Date: 2026-04-04 18:05:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260404_0013"
down_revision: str | None = "20260404_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


events_table = sa.table(
    "events",
    sa.column("id", sa.Uuid()),
    sa.column("job_id", sa.Uuid()),
    sa.column("actor_user_id", sa.Uuid()),
    sa.column("actor_org_id", sa.Uuid()),
    sa.column("assigned_org_id", sa.Uuid()),
    sa.column("assigned_contractor_user_id", sa.Uuid()),
    sa.column("location_id", sa.Uuid()),
    sa.column("asset_id", sa.Uuid()),
    sa.column("actor_name_snapshot", sa.Text()),
    sa.column("actor_role_snapshot", sa.Text()),
    sa.column("actor_org_name_snapshot", sa.Text()),
    sa.column("assigned_org_name_snapshot", sa.Text()),
    sa.column("assigned_contractor_name_snapshot", sa.Text()),
    sa.column("location_snapshot", sa.Text()),
    sa.column("asset_snapshot", sa.Text()),
)

users_table = sa.table(
    "users",
    sa.column("id", sa.Uuid()),
    sa.column("name", sa.Text()),
    sa.column("role", sa.Text()),
    sa.column("organisation_id", sa.Uuid()),
)

organisations_table = sa.table(
    "organisations",
    sa.column("id", sa.Uuid()),
    sa.column("name", sa.Text()),
)

locations_table = sa.table(
    "locations",
    sa.column("id", sa.Uuid()),
    sa.column("name", sa.Text()),
)

assets_table = sa.table(
    "assets",
    sa.column("id", sa.Uuid()),
    sa.column("name", sa.Text()),
)

jobs_table = sa.table(
    "jobs",
    sa.column("id", sa.Uuid()),
    sa.column("location_snapshot", sa.Text()),
    sa.column("asset_snapshot", sa.Text()),
)


def upgrade() -> None:
    with op.batch_alter_table("events", recreate="auto") as batch_op:
        batch_op.add_column(sa.Column("actor_name_snapshot", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("actor_role_snapshot", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("actor_org_name_snapshot", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("assigned_org_name_snapshot", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("assigned_contractor_name_snapshot", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("location_snapshot", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("asset_snapshot", sa.Text(), nullable=True))

    bind = op.get_bind()
    user_rows = bind.execute(
        sa.select(
            users_table.c.id,
            users_table.c.name,
            users_table.c.role,
            users_table.c.organisation_id,
        )
    ).all()
    organisation_name_by_id = dict(bind.execute(sa.select(organisations_table.c.id, organisations_table.c.name)).all())
    location_name_by_id = dict(bind.execute(sa.select(locations_table.c.id, locations_table.c.name)).all())
    asset_name_by_id = dict(bind.execute(sa.select(assets_table.c.id, assets_table.c.name)).all())
    job_snapshot_by_id = {
        row.id: {"location_snapshot": row.location_snapshot, "asset_snapshot": row.asset_snapshot}
        for row in bind.execute(
            sa.select(
                jobs_table.c.id,
                jobs_table.c.location_snapshot,
                jobs_table.c.asset_snapshot,
            )
        )
    }
    user_by_id = {
        row.id: {
            "name": row.name,
            "role": row.role,
            "organisation_name": organisation_name_by_id.get(row.organisation_id),
        }
        for row in user_rows
    }

    for row in bind.execute(
        sa.select(
            events_table.c.id,
            events_table.c.actor_user_id,
            events_table.c.actor_org_id,
            events_table.c.assigned_org_id,
            events_table.c.assigned_contractor_user_id,
            events_table.c.location_id,
            events_table.c.asset_id,
            events_table.c.job_id,
        )
    ):
        actor = user_by_id.get(row.actor_user_id)
        assigned_contractor = user_by_id.get(row.assigned_contractor_user_id)
        job_snapshot = job_snapshot_by_id.get(row.job_id, {})
        bind.execute(
            sa.update(events_table)
            .where(events_table.c.id == row.id)
            .values(
                actor_name_snapshot=actor["name"] if actor is not None else organisation_name_by_id.get(row.actor_org_id),
                actor_role_snapshot=actor["role"] if actor is not None else None,
                actor_org_name_snapshot=(
                    actor["organisation_name"]
                    if actor is not None
                    else organisation_name_by_id.get(row.actor_org_id)
                ),
                assigned_org_name_snapshot=organisation_name_by_id.get(row.assigned_org_id),
                assigned_contractor_name_snapshot=(
                    assigned_contractor["name"] if assigned_contractor is not None else None
                ),
                location_snapshot=job_snapshot.get("location_snapshot") or location_name_by_id.get(row.location_id),
                asset_snapshot=job_snapshot.get("asset_snapshot") or asset_name_by_id.get(row.asset_id),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("events", recreate="auto") as batch_op:
        batch_op.drop_column("asset_snapshot")
        batch_op.drop_column("location_snapshot")
        batch_op.drop_column("assigned_contractor_name_snapshot")
        batch_op.drop_column("assigned_org_name_snapshot")
        batch_op.drop_column("actor_org_name_snapshot")
        batch_op.drop_column("actor_role_snapshot")
        batch_op.drop_column("actor_name_snapshot")
