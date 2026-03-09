"""Align MVP schema with updated README contract.

Revision ID: 20260307_0002
Revises: 20260307_0001
Create Date: 2026-03-07 20:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260307_0002"
down_revision: str | None = "20260307_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _column_exists(table_name: str, column_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    columns = sa.inspect(op.get_bind()).get_columns(table_name)
    return any(column["name"] == column_name for column in columns)


def _index_exists(table_name: str, index_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    indexes = sa.inspect(op.get_bind()).get_indexes(table_name)
    return any(index["name"] == index_name for index in indexes)


def _drop_index_if_exists(table_name: str, index_name: str) -> None:
    if _index_exists(table_name, index_name):
        op.drop_index(index_name, table_name=table_name)


def _create_index_if_missing(table_name: str, index_name: str, columns: list[str]) -> None:
    if not _index_exists(table_name, index_name):
        op.create_index(index_name, table_name, columns)


def upgrade() -> None:
    if _column_exists("domain_events", "subject_type"):
        op.drop_column("domain_events", "subject_type")

    _drop_index_if_exists("maintenance_requests", "ix_maintenance_requests_org_created_at_desc")
    _drop_index_if_exists(
        "maintenance_requests",
        "ix_maintenance_requests_resident_created_at_desc",
    )
    _create_index_if_missing(
        "maintenance_requests",
        "ix_maintenance_requests_resident_created_at",
        ["resident_user_id", "created_at"],
    )

    _drop_index_if_exists("routing_rules", "ix_routing_rules_residence_category")
    _drop_index_if_exists("work_orders", "ix_work_orders_org_status")
    _drop_index_if_exists("domain_events", "ix_domain_events_subject_id")
    _drop_index_if_exists("domain_events", "ix_domain_events_type_time_desc")
    _drop_index_if_exists("integration_jobs", "ix_integration_jobs_work_order_id")

    op.execute("DROP TABLE IF EXISTS attachments CASCADE")
    op.execute("DROP TABLE IF EXISTS comments CASCADE")
    op.execute("DROP TABLE IF EXISTS photos CASCADE")


def downgrade() -> None:
    if _table_exists("domain_events") and not _column_exists("domain_events", "subject_type"):
        op.add_column(
            "domain_events",
            sa.Column(
                "subject_type",
                sa.Text(),
                nullable=False,
                server_default=sa.text("'unknown'"),
            ),
        )
        op.alter_column("domain_events", "subject_type", server_default=None)

    _drop_index_if_exists(
        "maintenance_requests",
        "ix_maintenance_requests_resident_created_at",
    )
    _create_index_if_missing(
        "maintenance_requests",
        "ix_maintenance_requests_org_created_at_desc",
        ["org_id", "created_at"],
    )
    _create_index_if_missing(
        "maintenance_requests",
        "ix_maintenance_requests_resident_created_at_desc",
        ["resident_user_id", "created_at"],
    )

    _create_index_if_missing(
        "routing_rules",
        "ix_routing_rules_residence_category",
        ["residence_id", "category"],
    )
    _create_index_if_missing("work_orders", "ix_work_orders_org_status", ["org_id", "status"])
    _create_index_if_missing("domain_events", "ix_domain_events_subject_id", ["subject_id"])
    _create_index_if_missing("domain_events", "ix_domain_events_type_time_desc", ["type", "time"])
    _create_index_if_missing(
        "integration_jobs",
        "ix_integration_jobs_work_order_id",
        ["work_order_id"],
    )
