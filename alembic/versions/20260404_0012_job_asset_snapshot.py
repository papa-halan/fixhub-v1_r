"""Preserve job asset labels as historical snapshots.

Revision ID: 20260404_0012
Revises: 20260404_0011
Create Date: 2026-04-04 16:55:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260404_0012"
down_revision: str | None = "20260404_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


jobs_table = sa.table(
    "jobs",
    sa.column("id", sa.Uuid()),
    sa.column("asset_id", sa.Uuid()),
    sa.column("asset_snapshot", sa.Text()),
)

assets_table = sa.table(
    "assets",
    sa.column("id", sa.Uuid()),
    sa.column("name", sa.Text()),
)


def upgrade() -> None:
    with op.batch_alter_table("jobs", recreate="auto") as batch_op:
        batch_op.add_column(sa.Column("asset_snapshot", sa.Text(), nullable=True))

    bind = op.get_bind()
    asset_name_by_id = dict(bind.execute(sa.select(assets_table.c.id, assets_table.c.name)).all())

    for job_id, asset_id in bind.execute(
        sa.select(jobs_table.c.id, jobs_table.c.asset_id).where(jobs_table.c.asset_id.is_not(None))
    ):
        asset_name = asset_name_by_id.get(asset_id)
        if asset_name is None:
            continue
        bind.execute(
            sa.update(jobs_table)
            .where(jobs_table.c.id == job_id)
            .values(asset_snapshot=asset_name)
        )


def downgrade() -> None:
    with op.batch_alter_table("jobs", recreate="auto") as batch_op:
        batch_op.drop_column("asset_snapshot")
