"""Add assignment snapshot fields to events.

Revision ID: 20260404_0010
Revises: 20260404_0009
Create Date: 2026-04-04 16:05:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260404_0010"
down_revision: str | None = "20260404_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("events", recreate="auto") as batch_op:
        batch_op.add_column(sa.Column("assigned_org_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("assigned_contractor_user_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_events_assigned_org_id_organisations",
            "organisations",
            ["assigned_org_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_events_assigned_contractor_user_id_users",
            "users",
            ["assigned_contractor_user_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("events", recreate="auto") as batch_op:
        batch_op.drop_constraint("fk_events_assigned_contractor_user_id_users", type_="foreignkey")
        batch_op.drop_constraint("fk_events_assigned_org_id_organisations", type_="foreignkey")
        batch_op.drop_column("assigned_contractor_user_id")
        batch_op.drop_column("assigned_org_id")
