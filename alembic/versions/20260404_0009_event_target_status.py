"""Add target status projection support to events.

Revision ID: 20260404_0009
Revises: 20260321_0008
Create Date: 2026-04-04 09:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session


revision: str = "20260404_0009"
down_revision: str | None = "20260321_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


job_status_enum = sa.Enum(
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

events_table = sa.table(
    "events",
    sa.column("id", sa.Uuid()),
    sa.column("event_type", sa.Text()),
    sa.column("message", sa.Text()),
    sa.column("target_status", job_status_enum),
)

DIRECT_TARGET_STATUS_BY_EVENT_TYPE = {
    "report_created": "new",
    "schedule": "scheduled",
    "completion": "completed",
    "follow_up": "follow_up_scheduled",
    "escalation": "escalated",
}

TARGET_STATUS_BY_STATUS_CHANGE_MESSAGE = {
    "Moved job back to new": "new",
    "Marked job assigned": "assigned",
    "Marked job triaged": "triaged",
    "Scheduled site visit": "scheduled",
    "Marked job in progress": "in_progress",
    "Placed job on hold": "on_hold",
    "Marked job blocked": "blocked",
    "Marked job completed": "completed",
    "Cancelled job": "cancelled",
    "Reopened job": "reopened",
    "Scheduled follow-up visit": "follow_up_scheduled",
    "Escalated job for review": "escalated",
}


def _target_status_for_event(event_type: str | None, message: str | None) -> str | None:
    if event_type in DIRECT_TARGET_STATUS_BY_EVENT_TYPE:
        return DIRECT_TARGET_STATUS_BY_EVENT_TYPE[event_type]
    if event_type == "status_change":
        return TARGET_STATUS_BY_STATUS_CHANGE_MESSAGE.get(message)
    return None


def upgrade() -> None:
    with op.batch_alter_table("events", recreate="auto") as batch_op:
        batch_op.add_column(sa.Column("target_status", job_status_enum, nullable=True))

    bind = op.get_bind()
    session = Session(bind=bind)
    event_rows = session.execute(
        sa.select(
            events_table.c.id,
            events_table.c.event_type,
            events_table.c.message,
        )
    ).all()

    for event_id, event_type, message in event_rows:
        target_status = _target_status_for_event(event_type, message)
        if target_status is None:
            continue
        session.execute(
            sa.update(events_table)
            .where(events_table.c.id == event_id)
            .values(target_status=target_status)
        )

    session.commit()


def downgrade() -> None:
    with op.batch_alter_table("events", recreate="auto") as batch_op:
        batch_op.drop_column("target_status")
