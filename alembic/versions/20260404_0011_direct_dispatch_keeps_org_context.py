"""Keep contractor organisation context on direct dispatch.

Revision ID: 20260404_0011
Revises: 20260404_0010
Create Date: 2026-04-04 16:20:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260404_0011"
down_revision: str | None = "20260404_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


jobs_table = sa.table(
    "jobs",
    sa.column("id", sa.Uuid()),
    sa.column("assigned_org_id", sa.Uuid()),
    sa.column("assigned_contractor_user_id", sa.Uuid()),
)

users_table = sa.table(
    "users",
    sa.column("id", sa.Uuid()),
    sa.column("organisation_id", sa.Uuid()),
)


def upgrade() -> None:
    with op.batch_alter_table("jobs", recreate="auto") as batch_op:
        batch_op.drop_constraint("ck_jobs_single_assignee", type_="check")

    bind = op.get_bind()
    direct_dispatch_rows = bind.execute(
        sa.select(users_table.c.id, users_table.c.organisation_id).where(users_table.c.organisation_id.is_not(None))
    ).all()
    organisation_by_user_id = {user_id: organisation_id for user_id, organisation_id in direct_dispatch_rows}

    for job_id, assigned_org_id, assigned_contractor_user_id in bind.execute(
        sa.select(
            jobs_table.c.id,
            jobs_table.c.assigned_org_id,
            jobs_table.c.assigned_contractor_user_id,
        ).where(
            jobs_table.c.assigned_contractor_user_id.is_not(None),
            jobs_table.c.assigned_org_id.is_(None),
        )
    ):
        contractor_org_id = organisation_by_user_id.get(assigned_contractor_user_id)
        if contractor_org_id is None:
            continue
        bind.execute(
            sa.update(jobs_table)
            .where(jobs_table.c.id == job_id)
            .values(assigned_org_id=contractor_org_id)
        )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.update(jobs_table)
        .where(jobs_table.c.assigned_contractor_user_id.is_not(None))
        .values(assigned_org_id=None)
    )

    with op.batch_alter_table("jobs", recreate="auto") as batch_op:
        batch_op.create_check_constraint(
            "ck_jobs_single_assignee",
            "NOT (assigned_org_id IS NOT NULL AND assigned_contractor_user_id IS NOT NULL)",
        )
