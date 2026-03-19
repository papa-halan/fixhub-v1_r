from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, created_timestamp, uuid_pk

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.job import Job
    from app.models.location import Location


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (
        UniqueConstraint("location_id", "name", name="uq_assets_location_name"),
        Index("ix_assets_location_id_name", "location_id", "name"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    location_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("locations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = created_timestamp()

    location_record: Mapped[Location] = relationship(back_populates="assets")
    jobs: Mapped[list[Job]] = relationship(back_populates="asset")
    events: Mapped[list[Event]] = relationship(back_populates="asset")
