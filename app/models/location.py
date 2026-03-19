from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, created_timestamp, uuid_pk

if TYPE_CHECKING:
    from app.models.asset import Asset
    from app.models.event import Event
    from app.models.job import Job
    from app.models.user import User


class Location(Base):
    __tablename__ = "locations"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_locations_user_name"),
        Index("ix_locations_user_id_name", "user_id", "name"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = created_timestamp()

    user: Mapped[User] = relationship(back_populates="locations")
    assets: Mapped[list[Asset]] = relationship(
        back_populates="location_record",
        cascade="all, delete-orphan",
        order_by="Asset.name",
    )
    jobs: Mapped[list[Job]] = relationship(back_populates="location_record")
    events: Mapped[list[Event]] = relationship(back_populates="location_record")
