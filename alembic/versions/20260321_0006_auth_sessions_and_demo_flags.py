"""Add password-based auth fields and demo-account flags.

Revision ID: 20260321_0006
Revises: 20260319_0005
Create Date: 2026-03-21 17:20:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260321_0006"
down_revision: str | None = "20260319_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


DEMO_EMAILS = (
    "resident@fixhub.test",
    "admin@fixhub.test",
    "reception@fixhub.test",
    "triage@fixhub.test",
    "coordinator@fixhub.test",
    "contractor@fixhub.test",
    "maintenance.contractor@fixhub.test",
    "independent.contractor@fixhub.test",
)


def upgrade() -> None:
    with op.batch_alter_table("users", recreate="auto") as batch_op:
        batch_op.add_column(sa.Column("password_hash", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("is_demo_account", sa.Boolean(), nullable=False, server_default=sa.false())
        )

    users_table = sa.table(
        "users",
        sa.column("email", sa.Text()),
        sa.column("is_demo_account", sa.Boolean()),
    )
    op.execute(
        sa.update(users_table)
        .where(users_table.c.email.in_(DEMO_EMAILS))
        .values(is_demo_account=True)
    )


def downgrade() -> None:
    with op.batch_alter_table("users", recreate="auto") as batch_op:
        batch_op.drop_column("is_demo_account")
        batch_op.drop_column("password_hash")
