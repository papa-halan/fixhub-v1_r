"""Add operational workflow roles, direct assignment, and accountability metadata.

Revision ID: 20260319_0005
Revises: 20260319_0004
Create Date: 2026-03-19 17:10:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260319_0005"
down_revision: str | None = "20260319_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


old_user_role = sa.Enum(
    "resident",
    "admin",
    "contractor",
    name="user_role_enum",
    native_enum=False,
)
new_user_role = sa.Enum(
    "resident",
    "admin",
    "reception_admin",
    "triage_officer",
    "coordinator",
    "contractor",
    name="user_role_enum",
    native_enum=False,
)
old_job_status = sa.Enum(
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
new_job_status = sa.Enum(
    "new",
    "assigned",
    "triaged",
    "scheduled",
    "in_progress",
    "on_hold",
    "blocked",
    "completed",
    "cancelled",
    "reopened",
    "follow_up_scheduled",
    "escalated",
    name="job_status_enum",
    native_enum=False,
)
contractor_mode_enum = sa.Enum(
    "maintenance_team",
    "external_contractor",
    name="contractor_mode_enum",
    native_enum=False,
)
event_type_enum = sa.Enum(
    "report_created",
    "note",
    "assignment",
    "status_change",
    "schedule",
    "escalation",
    "completion",
    "follow_up",
    name="event_type_enum",
    native_enum=False,
)
responsibility_stage_enum = sa.Enum(
    "reception",
    "triage",
    "coordination",
    "execution",
    name="responsibility_stage_enum",
    native_enum=False,
)
owner_scope_enum = sa.Enum(
    "organisation",
    "user",
    name="owner_scope_enum",
    native_enum=False,
)


def upgrade() -> None:
    with op.batch_alter_table("organisations", recreate="auto") as batch_op:
        batch_op.add_column(sa.Column("parent_org_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("contractor_mode", contractor_mode_enum, nullable=True))
        batch_op.create_foreign_key(
            "fk_organisations_parent_org_id_organisations",
            "organisations",
            ["parent_org_id"],
            ["id"],
        )
        batch_op.create_index("ix_organisations_parent_org_id", ["parent_org_id"])

    with op.batch_alter_table("users", recreate="auto") as batch_op:
        batch_op.alter_column(
            "role",
            existing_type=old_user_role,
            type_=new_user_role,
            existing_nullable=False,
        )

    with op.batch_alter_table("jobs", recreate="auto") as batch_op:
        batch_op.add_column(sa.Column("assigned_contractor_user_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_jobs_assigned_contractor_user_id_users",
            "users",
            ["assigned_contractor_user_id"],
            ["id"],
        )
        batch_op.create_index(
            "ix_jobs_assigned_contractor_status",
            ["assigned_contractor_user_id", "status"],
        )
        batch_op.create_check_constraint(
            "ck_jobs_single_assignee",
            "NOT (assigned_org_id IS NOT NULL AND assigned_contractor_user_id IS NOT NULL)",
        )
        batch_op.alter_column(
            "status",
            existing_type=old_job_status,
            type_=new_job_status,
            existing_nullable=False,
            server_default="new",
        )

    with op.batch_alter_table("events", recreate="auto") as batch_op:
        batch_op.add_column(
            sa.Column(
                "event_type",
                event_type_enum,
                nullable=False,
                server_default="note",
            )
        )
        batch_op.add_column(sa.Column("responsibility_stage", responsibility_stage_enum, nullable=True))
        batch_op.add_column(sa.Column("owner_scope", owner_scope_enum, nullable=True))
        batch_op.create_index(
            "ix_events_job_event_type_created_at",
            ["job_id", "event_type", "created_at"],
        )

    op.execute(
        sa.text(
            """
            UPDATE organisations
            SET contractor_mode = 'external_contractor'
            WHERE type = 'contractor' AND contractor_mode IS NULL
            """
        )
    )

    op.execute(
        sa.text(
            """
            UPDATE events
            SET event_type = CASE
                WHEN message = 'Report created' THEN 'report_created'
                WHEN message = 'Marked job completed' THEN 'completion'
                WHEN message = 'Scheduled site visit' THEN 'schedule'
                WHEN message = 'Scheduled follow-up visit' THEN 'follow_up'
                WHEN message = 'Escalated job for review' THEN 'escalation'
                WHEN message LIKE 'Assigned %'
                  OR message LIKE 'Reassigned %'
                  OR message = 'Assignment cleared'
                  OR message = 'Marked job assigned'
                    THEN 'assignment'
                WHEN message LIKE 'Marked job %'
                  OR message LIKE 'Moved job %'
                  OR message = 'Placed job on hold'
                  OR message = 'Cancelled job'
                  OR message = 'Reopened job'
                    THEN 'status_change'
                ELSE 'note'
            END
            """
        )
    )

    op.execute(
        sa.text(
            """
            UPDATE events
            SET responsibility_stage = CASE
                WHEN responsibility_owner IN ('reception_admin', 'resident') THEN 'reception'
                WHEN responsibility_owner = 'triage_officer' THEN 'triage'
                WHEN responsibility_owner = 'coordinator' THEN 'coordination'
                WHEN responsibility_owner = 'contractor' THEN 'execution'
                WHEN event_type = 'report_created' THEN 'reception'
                WHEN event_type = 'assignment' THEN 'triage'
                WHEN event_type = 'schedule' THEN 'coordination'
                WHEN event_type = 'follow_up' THEN 'coordination'
                WHEN event_type = 'completion' THEN 'execution'
                WHEN event_type = 'escalation' THEN 'triage'
                WHEN message IN ('Marked job in progress', 'Marked job blocked') THEN 'execution'
                ELSE 'coordination'
            END
            WHERE responsibility_stage IS NULL
            """
        )
    )

    op.execute(
        sa.text(
            """
            UPDATE events
            SET owner_scope = CASE
                WHEN actor_org_id IS NOT NULL THEN 'organisation'
                ELSE 'user'
            END
            WHERE owner_scope IS NULL
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE jobs
            SET status = CASE
                WHEN status IN ('triaged', 'scheduled') THEN 'assigned'
                WHEN status = 'follow_up_scheduled' THEN 'reopened'
                WHEN status = 'escalated' THEN 'on_hold'
                ELSE status
            END
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE users
            SET role = 'admin'
            WHERE role IN ('reception_admin', 'triage_officer', 'coordinator')
            """
        )
    )

    with op.batch_alter_table("events", recreate="auto") as batch_op:
        batch_op.drop_index("ix_events_job_event_type_created_at")
        batch_op.drop_column("owner_scope")
        batch_op.drop_column("responsibility_stage")
        batch_op.drop_column("event_type")

    with op.batch_alter_table("jobs", recreate="auto") as batch_op:
        batch_op.drop_constraint("ck_jobs_single_assignee", type_="check")
        batch_op.drop_index("ix_jobs_assigned_contractor_status")
        batch_op.drop_constraint("fk_jobs_assigned_contractor_user_id_users", type_="foreignkey")
        batch_op.drop_column("assigned_contractor_user_id")
        batch_op.alter_column(
            "status",
            existing_type=new_job_status,
            type_=old_job_status,
            existing_nullable=False,
            server_default="new",
        )

    with op.batch_alter_table("users", recreate="auto") as batch_op:
        batch_op.alter_column(
            "role",
            existing_type=new_user_role,
            type_=old_user_role,
            existing_nullable=False,
        )

    with op.batch_alter_table("organisations", recreate="auto") as batch_op:
        batch_op.drop_index("ix_organisations_parent_org_id")
        batch_op.drop_constraint("fk_organisations_parent_org_id_organisations", type_="foreignkey")
        batch_op.drop_column("contractor_mode")
        batch_op.drop_column("parent_org_id")
