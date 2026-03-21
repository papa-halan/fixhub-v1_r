from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, created_timestamp, uuid_pk
from app.models.enums import LocationType

if TYPE_CHECKING:
    from app.models.asset import Asset
    from app.models.event import Event
    from app.models.job import Job
    from app.models.organisation import Organisation


class Location(Base):
    __tablename__ = "locations"
    __table_args__ = (
        UniqueConstraint("organisation_id", "name", name="uq_locations_organisation_name"),
        Index("ix_locations_organisation_id_name", "organisation_id", "name"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisations.id"),
        nullable=False,
        index=True,
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("locations.id"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[LocationType] = mapped_column(
        Enum(LocationType, name="location_type_enum", native_enum=False, validate_strings=True),
        nullable=False,
        default=LocationType.space,
        server_default=LocationType.space.value,
    )
    created_at: Mapped[datetime] = created_timestamp()

    organisation: Mapped[Organisation] = relationship(back_populates="locations")
    parent: Mapped[Location | None] = relationship(
        remote_side="Location.id",
        back_populates="children",
        foreign_keys=[parent_id],
    )
    children: Mapped[list[Location]] = relationship(
        back_populates="parent",
        order_by="Location.name",
    )
    assets: Mapped[list[Asset]] = relationship(
        back_populates="location_record",
        cascade="all, delete-orphan",
        order_by="Asset.name",
    )
    jobs: Mapped[list[Job]] = relationship(back_populates="location")
    events: Mapped[list[Event]] = relationship(back_populates="location_record")
