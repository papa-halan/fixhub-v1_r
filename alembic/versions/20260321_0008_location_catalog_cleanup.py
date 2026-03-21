"""Remove legacy placeholder locations from the active catalog.

Revision ID: 20260321_0008
Revises: 20260321_0007
Create Date: 2026-03-21 21:40:00
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session


revision: str = "20260321_0008"
down_revision: str | None = "20260321_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


locations_table = sa.table(
    "locations",
    sa.column("id", sa.Uuid()),
    sa.column("parent_id", sa.Uuid()),
    sa.column("name", sa.Text()),
    sa.column("type", sa.Text()),
)

jobs_table = sa.table(
    "jobs",
    sa.column("location_id", sa.Uuid()),
)

assets_table = sa.table(
    "assets",
    sa.column("location_id", sa.Uuid()),
)

events_table = sa.table(
    "events",
    sa.column("location_id", sa.Uuid()),
)


PLACEHOLDER_NAMES = {"", "-", ".", "?", "n/a", "na", "none", "null", "unknown"}


def _normalize_name(name: str | None) -> str:
    return " ".join((name or "").strip().lower().split())


def _is_placeholder_location(name: str | None) -> bool:
    normalized = _normalize_name(name)
    if normalized in PLACEHOLDER_NAMES:
        return True
    return len(normalized) == 1 and normalized.isalpha()


def upgrade() -> None:
    bind = op.get_bind()
    session = Session(bind=bind)

    candidate_rows = session.execute(
        sa.select(
            locations_table.c.id,
            locations_table.c.name,
        ).where(
            locations_table.c.parent_id.is_(None),
            locations_table.c.type.in_(("space", "unit")),
        )
    ).all()

    for location_id, name in candidate_rows:
        if not _is_placeholder_location(name):
            continue

        has_job = session.execute(
            sa.select(sa.literal(True)).where(jobs_table.c.location_id == location_id).limit(1)
        ).scalar_one_or_none()
        has_asset = session.execute(
            sa.select(sa.literal(True)).where(assets_table.c.location_id == location_id).limit(1)
        ).scalar_one_or_none()
        has_event = session.execute(
            sa.select(sa.literal(True)).where(events_table.c.location_id == location_id).limit(1)
        ).scalar_one_or_none()

        if has_job or has_asset or has_event:
            session.execute(
                sa.update(locations_table)
                .where(locations_table.c.id == location_id)
                .values(type="building")
            )
        else:
            session.execute(sa.delete(locations_table).where(locations_table.c.id == location_id))

    session.commit()


def downgrade() -> None:
    bind = op.get_bind()
    session = Session(bind=bind)

    candidate_rows = session.execute(
        sa.select(
            locations_table.c.id,
            locations_table.c.name,
            locations_table.c.type,
        ).where(
            locations_table.c.parent_id.is_(None),
            locations_table.c.type == "building",
        )
    ).all()

    for location_id, name, _location_type in candidate_rows:
        if _is_placeholder_location(name):
            session.execute(
                sa.update(locations_table)
                .where(locations_table.c.id == location_id)
                .values(type="space")
            )

    session.commit()
