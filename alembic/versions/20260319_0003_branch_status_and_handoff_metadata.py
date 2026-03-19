"""Extend job status lifecycle and add branch handoff metadata.

Revision ID: 20260319_0003
Revises: 20260315_0002
Create Date: 2026-03-19 14:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260319_0003"
down_revision: str | None = "20260315_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


old_job_status = sa.Enum(
    "new",
    "assigned",
    "in_progress",
    "completed",
    name="job_status_enum",
    native_enum=False,
)
new_job_status = sa.Enum(
    "new",
    "assigned",
    "in_progress",
    "on_hold",
    "blocked",
    "completed",
    "cancelled",
    "reopened",
    name="job_status_enum",
    native_enum=False,
)
responsibility_owner_enum = sa.Enum(
    "reception_admin",
    "triage_officer",
    "coordinator",
    "contractor",
    "resident",
    name="responsibility_owner_enum",
    native_enum=False,
)


def upgrade() -> None:
    with op.batch_alter_table("events", recreate="auto") as batch_op:
        batch_op.add_column(sa.Column("reason_code", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("responsibility_owner", responsibility_owner_enum, nullable=True))

    with op.batch_alter_table("jobs", recreate="auto") as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=old_job_status,
            type_=new_job_status,
            existing_nullable=False,
            server_default="new",
        )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE jobs
            SET status = CASE
                WHEN status = 'on_hold' THEN 'in_progress'
                WHEN status = 'blocked' THEN 'in_progress'
                WHEN status = 'cancelled' THEN 'new'
                WHEN status = 'reopened' THEN 'in_progress'
                ELSE status
            END
            """
        )
    )

    with op.batch_alter_table("jobs", recreate="auto") as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=new_job_status,
            type_=old_job_status,
            existing_nullable=False,
            server_default="new",
        )

    with op.batch_alter_table("events", recreate="auto") as batch_op:
        batch_op.drop_column("responsibility_owner")
        batch_op.drop_column("reason_code")
