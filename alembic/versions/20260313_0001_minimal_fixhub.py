"""Create the minimal FixHub schema.

Revision ID: 20260313_0001
Revises:
Create Date: 2026-03-13 18:10:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260313_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


user_role = sa.Enum(
    "resident",
    "admin",
    "contractor",
    name="user_role_enum",
    native_enum=False,
)
organisation_type = sa.Enum(
    "university",
    "contractor",
    name="organisation_type_enum",
    native_enum=False,
)
job_status = sa.Enum(
    "new",
    "assigned",
    "in_progress",
    "completed",
    name="job_status_enum",
    native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "organisations",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("type", organisation_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organisation_id"], ["organisations.id"]),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_organisation_id", "users", ["organisation_id"])

    op.create_table(
        "jobs",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("location", sa.Text(), nullable=False),
        sa.Column("status", job_status, nullable=False, server_default="new"),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("assigned_org_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["assigned_org_id"], ["organisations.id"]),
    )
    op.create_index("ix_jobs_created_by_created_at", "jobs", ["created_by", "created_at"])
    op.create_index("ix_jobs_assigned_org_status", "jobs", ["assigned_org_id", "status"])

    op.create_table(
        "events",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("actor_org_id", sa.Uuid(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["actor_org_id"], ["organisations.id"]),
    )
    op.create_index("ix_events_job_created_at", "events", ["job_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_events_job_created_at", table_name="events")
    op.drop_table("events")
    op.drop_index("ix_jobs_assigned_org_status", table_name="jobs")
    op.drop_index("ix_jobs_created_by_created_at", table_name="jobs")
    op.drop_table("jobs")
    op.drop_index("ix_users_organisation_id", table_name="users")
    op.drop_table("users")
    op.drop_table("organisations")
