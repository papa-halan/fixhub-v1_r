"""Add stable job actor and subject name snapshots.

Revision ID: 20260410_0016
Revises: 20260404_0015
Create Date: 2026-04-10 18:20:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260410_0016"
down_revision: str | None = "20260404_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


jobs_table = sa.table(
    "jobs",
    sa.column("id", sa.Uuid()),
    sa.column("created_by", sa.Uuid()),
    sa.column("reported_for_user_id", sa.Uuid()),
    sa.column("created_by_name_snapshot", sa.Text()),
    sa.column("reported_for_user_name_snapshot", sa.Text()),
)

events_table = sa.table(
    "events",
    sa.column("job_id", sa.Uuid()),
    sa.column("event_type", sa.Text()),
    sa.column("actor_name_snapshot", sa.Text()),
)

users_table = sa.table(
    "users",
    sa.column("id", sa.Uuid()),
    sa.column("name", sa.Text()),
)


def upgrade() -> None:
    with op.batch_alter_table("jobs", recreate="auto") as batch_op:
        batch_op.add_column(sa.Column("created_by_name_snapshot", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("reported_for_user_name_snapshot", sa.Text(), nullable=True))

    bind = op.get_bind()
    creator_name_from_report_event = (
        sa.select(events_table.c.actor_name_snapshot)
        .where(
            events_table.c.job_id == jobs_table.c.id,
            events_table.c.event_type == "report_created",
            events_table.c.actor_name_snapshot.is_not(None),
        )
        .limit(1)
        .scalar_subquery()
    )
    creator_name_from_user = (
        sa.select(users_table.c.name)
        .where(users_table.c.id == jobs_table.c.created_by)
        .limit(1)
        .scalar_subquery()
    )
    reported_for_name_from_user = (
        sa.select(users_table.c.name)
        .where(users_table.c.id == jobs_table.c.reported_for_user_id)
        .limit(1)
        .scalar_subquery()
    )

    bind.execute(
        sa.update(jobs_table).values(
            created_by_name_snapshot=sa.func.coalesce(
                creator_name_from_report_event,
                creator_name_from_user,
            ),
            reported_for_user_name_snapshot=reported_for_name_from_user,
        )
    )

    with op.batch_alter_table("jobs", recreate="auto") as batch_op:
        batch_op.alter_column("created_by_name_snapshot", existing_type=sa.Text(), nullable=False)
        batch_op.alter_column("reported_for_user_name_snapshot", existing_type=sa.Text(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("jobs", recreate="auto") as batch_op:
        batch_op.drop_column("reported_for_user_name_snapshot")
        batch_op.drop_column("created_by_name_snapshot")
