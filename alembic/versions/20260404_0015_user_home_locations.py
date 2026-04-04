"""Add resident home location anchor.

Revision ID: 20260404_0015
Revises: 20260404_0014
Create Date: 2026-04-04 23:55:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260404_0015"
down_revision: str | None = "20260404_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users", recreate="auto") as batch_op:
        batch_op.add_column(sa.Column("home_location_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_users_home_location_id_locations",
            "locations",
            ["home_location_id"],
            ["id"],
        )
        batch_op.create_index("ix_users_home_location_id", ["home_location_id"])


def downgrade() -> None:
    with op.batch_alter_table("users", recreate="auto") as batch_op:
        batch_op.drop_index("ix_users_home_location_id")
        batch_op.drop_constraint("fk_users_home_location_id_locations", type_="foreignkey")
        batch_op.drop_column("home_location_id")
