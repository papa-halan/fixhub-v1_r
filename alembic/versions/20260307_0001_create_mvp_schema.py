"""Create maintenance coordination MVP schema.

Revision ID: 20260307_0001
Revises: 
Create Date: 2026-03-07 14:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260307_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


USER_ROLE_ENUM = sa.Enum("resident", "contractor", "staff", name="user_role_enum")
WORK_ORDER_STATUS_ENUM = sa.Enum(
    "assigned", "in_progress", "completed", name="work_order_status_enum"
)
INTEGRATION_JOB_STATUS_ENUM = sa.Enum(
    "requested", "completed", "failed", name="integration_job_status_enum"
)


EVENT_TYPE_CHECK = (
    "type IN ("
    "'uon.maintenance_request.submitted',"
    "'uon.work_order.created',"
    "'uon.work_order.status_changed',"
    "'uon.integration.requested',"
    "'uon.integration.completed',"
    "'uon.integration.failed'"
    ")"
)


def upgrade() -> None:
    bind = op.get_bind()
    USER_ROLE_ENUM.create(bind, checkfirst=True)
    WORK_ORDER_STATUS_ENUM.create(bind, checkfirst=True)
    INTEGRATION_JOB_STATUS_ENUM.create(bind, checkfirst=True)

    op.create_table(
        "organisations",
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("org_id"),
    )

    op.create_table(
        "residences",
        sa.Column("residence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organisations.org_id"]),
        sa.PrimaryKeyConstraint("residence_id"),
    )

    op.create_table(
        "units",
        sa.Column("unit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("residence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["residence_id"], ["residences.residence_id"]),
        sa.PrimaryKeyConstraint("unit_id"),
    )

    op.create_table(
        "users",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", USER_ROLE_ENUM, nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["org_id"], ["organisations.org_id"]),
        sa.PrimaryKeyConstraint("user_id"),
        sa.UniqueConstraint("email"),
    )

    op.create_table(
        "maintenance_requests",
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("unit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resident_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("priority", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["org_id"], ["organisations.org_id"]),
        sa.ForeignKeyConstraint(["unit_id"], ["units.unit_id"]),
        sa.ForeignKeyConstraint(["resident_user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("request_id"),
    )

    op.create_table(
        "routing_rules",
        sa.Column("rule_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("residence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("contractor_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["org_id"], ["organisations.org_id"]),
        sa.ForeignKeyConstraint(["residence_id"], ["residences.residence_id"]),
        sa.ForeignKeyConstraint(["contractor_user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("rule_id"),
        sa.UniqueConstraint(
            "residence_id",
            "category",
            name="uq_routing_rules_residence_category",
        ),
    )

    op.create_table(
        "work_orders",
        sa.Column("work_order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contractor_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            WORK_ORDER_STATUS_ENUM,
            nullable=False,
            server_default="assigned",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organisations.org_id"]),
        sa.ForeignKeyConstraint(["request_id"], ["maintenance_requests.request_id"]),
        sa.ForeignKeyConstraint(["contractor_user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("work_order_id"),
        sa.UniqueConstraint("request_id", name="uq_work_orders_request_id"),
    )

    op.create_table(
        "domain_events",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("subject_type", sa.Text(), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "time",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("partition_key", sa.Text(), nullable=False),
        sa.Column("routing_key", sa.Text(), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.CheckConstraint(EVENT_TYPE_CHECK, name="ck_domain_events_type"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("event_id"),
    )

    op.create_table(
        "integration_jobs",
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("work_order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connector", sa.Text(), nullable=False),
        sa.Column(
            "status",
            INTEGRATION_JOB_STATUS_ENUM,
            nullable=False,
            server_default="requested",
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["event_id"], ["domain_events.event_id"]),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.work_order_id"]),
        sa.PrimaryKeyConstraint("job_id"),
    )

    op.create_table(
        "audit_entries",
        sa.Column("audit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["event_id"], ["domain_events.event_id"]),
        sa.PrimaryKeyConstraint("audit_id"),
        sa.UniqueConstraint("event_id"),
    )

    op.create_index(
        "ix_routing_rules_residence_category",
        "routing_rules",
        ["residence_id", "category"],
    )
    op.create_index(
        "ix_work_orders_contractor_status",
        "work_orders",
        ["contractor_user_id", "status"],
    )
    op.create_index("ix_work_orders_org_status", "work_orders", ["org_id", "status"])

    op.create_index(
        "ix_domain_events_partition_time",
        "domain_events",
        ["partition_key", "time"],
    )
    op.create_index("ix_domain_events_subject_id", "domain_events", ["subject_id"])
    op.create_index(
        "ix_integration_jobs_status_created",
        "integration_jobs",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_integration_jobs_work_order_id",
        "integration_jobs",
        ["work_order_id"],
    )

    op.execute(
        "CREATE INDEX ix_maintenance_requests_org_created_at_desc "
        "ON maintenance_requests (org_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX ix_maintenance_requests_resident_created_at_desc "
        "ON maintenance_requests (resident_user_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX ix_domain_events_type_time_desc "
        "ON domain_events (type, time DESC)"
    )


def downgrade() -> None:
    op.drop_table("audit_entries")
    op.drop_table("integration_jobs")
    op.drop_table("domain_events")
    op.drop_table("work_orders")
    op.drop_table("routing_rules")
    op.drop_table("maintenance_requests")
    op.drop_table("users")
    op.drop_table("units")
    op.drop_table("residences")
    op.drop_table("organisations")

    bind = op.get_bind()
    INTEGRATION_JOB_STATUS_ENUM.drop(bind, checkfirst=True)
    WORK_ORDER_STATUS_ENUM.drop(bind, checkfirst=True)
    USER_ROLE_ENUM.drop(bind, checkfirst=True)