"""Add structured location hierarchy and job organisation scope.

Revision ID: 20260321_0007
Revises: 20260321_0006
Create Date: 2026-03-21 17:45:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session


revision: str = "20260321_0007"
down_revision: str | None = "20260321_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


location_type_enum = sa.Enum(
    "site",
    "building",
    "space",
    "unit",
    name="location_type_enum",
    native_enum=False,
)

jobs_table = sa.table(
    "jobs",
    sa.column("id", sa.Uuid()),
    sa.column("created_by", sa.Uuid()),
    sa.column("organisation_id", sa.Uuid()),
    sa.column("location_id", sa.Uuid()),
)

locations_table = sa.table(
    "locations",
    sa.column("id", sa.Uuid()),
    sa.column("organisation_id", sa.Uuid()),
    sa.column("type", location_type_enum),
)

users_table = sa.table(
    "users",
    sa.column("id", sa.Uuid()),
    sa.column("organisation_id", sa.Uuid()),
)


def upgrade() -> None:
    with op.batch_alter_table("locations", recreate="auto") as batch_op:
        batch_op.add_column(sa.Column("parent_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("type", location_type_enum, nullable=True))
        batch_op.create_foreign_key(
            "fk_locations_parent_id_locations",
            "locations",
            ["parent_id"],
            ["id"],
        )

    op.execute(sa.text("UPDATE locations SET type = 'space' WHERE type IS NULL"))

    with op.batch_alter_table("locations", recreate="auto") as batch_op:
        batch_op.alter_column(
            "type",
            existing_type=location_type_enum,
            nullable=False,
            server_default="space",
        )
        batch_op.create_index("ix_locations_parent_id", ["parent_id"])

    with op.batch_alter_table("jobs", recreate="auto") as batch_op:
        batch_op.add_column(sa.Column("organisation_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("location_detail_text", sa.Text(), nullable=True))
        batch_op.create_foreign_key(
            "fk_jobs_organisation_id_organisations",
            "organisations",
            ["organisation_id"],
            ["id"],
        )
        batch_op.create_index("ix_jobs_organisation_id", ["organisation_id"])

    bind = op.get_bind()
    session = Session(bind=bind)
    location_org_subquery = (
        sa.select(locations_table.c.organisation_id)
        .where(locations_table.c.id == jobs_table.c.location_id)
        .scalar_subquery()
    )
    creator_org_subquery = (
        sa.select(users_table.c.organisation_id)
        .where(users_table.c.id == jobs_table.c.created_by)
        .scalar_subquery()
    )
    session.execute(
        sa.update(jobs_table).values(
            organisation_id=sa.func.coalesce(location_org_subquery, creator_org_subquery)
        )
    )
    session.commit()

    missing_count = session.execute(
        sa.select(sa.func.count()).select_from(jobs_table).where(jobs_table.c.organisation_id.is_(None))
    ).scalar_one()
    if missing_count:
        raise RuntimeError("Cannot backfill jobs.organisation_id for all rows")

    with op.batch_alter_table("jobs", recreate="auto") as batch_op:
        batch_op.alter_column("organisation_id", existing_type=sa.Uuid(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("jobs", recreate="auto") as batch_op:
        batch_op.drop_index("ix_jobs_organisation_id")
        batch_op.drop_constraint("fk_jobs_organisation_id_organisations", type_="foreignkey")
        batch_op.drop_column("location_detail_text")
        batch_op.drop_column("organisation_id")

    with op.batch_alter_table("locations", recreate="auto") as batch_op:
        batch_op.drop_index("ix_locations_parent_id")
        batch_op.drop_constraint("fk_locations_parent_id_locations", type_="foreignkey")
        batch_op.drop_column("type")
        batch_op.drop_column("parent_id")
