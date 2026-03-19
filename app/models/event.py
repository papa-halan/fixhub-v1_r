from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, created_timestamp, uuid_pk

if TYPE_CHECKING:
    from app.models.asset import Asset
    from app.models.job import Job
    from app.models.location import Location
    from app.models.organisation import Organisation
    from app.models.user import User


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_job_created_at", "job_id", "created_at"),
        Index("ix_events_location_asset_created_at", "location_id", "asset_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    actor_org_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organisations.id"),
        nullable=True,
    )
    location_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("locations.id"), nullable=True)
    asset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("assets.id"), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = created_timestamp()

    job: Mapped[Job] = relationship(back_populates="events")
    actor_user: Mapped[User | None] = relationship(
        back_populates="events",
        foreign_keys=[actor_user_id],
    )
    actor_org: Mapped[Organisation | None] = relationship(foreign_keys=[actor_org_id])
    location_record: Mapped[Location | None] = relationship(
        back_populates="events",
        foreign_keys=[location_id],
    )
    asset: Mapped[Asset | None] = relationship(
        back_populates="events",
        foreign_keys=[asset_id],
    )
