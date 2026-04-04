"""Split job creator from resident subject.

Revision ID: 20260404_0014
Revises: 20260404_0013
Create Date: 2026-04-04 23:20:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260404_0014"
down_revision: str | None = "20260404_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


jobs_table = sa.table(
    "jobs",
    sa.column("id", sa.Uuid()),
    sa.column("created_by", sa.Uuid()),
    sa.column("reported_for_user_id", sa.Uuid()),
)

events_table = sa.table(
    "events",
    sa.column("job_id", sa.Uuid()),
    sa.column("actor_user_id", sa.Uuid()),
    sa.column("event_type", sa.Text()),
)


def upgrade() -> None:
    with op.batch_alter_table("jobs", recreate="auto") as batch_op:
        batch_op.add_column(sa.Column("reported_for_user_id", sa.Uuid(), nullable=True))

    bind = op.get_bind()
    report_actor_subquery = (
        sa.select(events_table.c.actor_user_id)
        .where(
            events_table.c.job_id == jobs_table.c.id,
            events_table.c.event_type == "report_created",
            events_table.c.actor_user_id.is_not(None),
        )
        .limit(1)
        .scalar_subquery()
    )

    bind.execute(
        sa.update(jobs_table).values(
            reported_for_user_id=jobs_table.c.created_by,
            created_by=sa.func.coalesce(report_actor_subquery, jobs_table.c.created_by),
        )
    )

    with op.batch_alter_table("jobs", recreate="auto") as batch_op:
        batch_op.create_foreign_key(
            "fk_jobs_reported_for_user_id_users",
            "users",
            ["reported_for_user_id"],
            ["id"],
        )
        batch_op.create_index("ix_jobs_reported_for_created_at", ["reported_for_user_id", "created_at"])
        batch_op.alter_column("reported_for_user_id", existing_type=sa.Uuid(), nullable=False)


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.update(jobs_table).values(created_by=jobs_table.c.reported_for_user_id))

    with op.batch_alter_table("jobs", recreate="auto") as batch_op:
        batch_op.drop_index("ix_jobs_reported_for_created_at")
        batch_op.drop_constraint("fk_jobs_reported_for_user_id_users", type_="foreignkey")
        batch_op.drop_column("reported_for_user_id")
