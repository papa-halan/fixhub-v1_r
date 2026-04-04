from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, created_timestamp, uuid_pk
from app.models.enums import EventType, JobStatus, OwnerScope, ResponsibilityOwner, ResponsibilityStage

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
        Index("ix_events_job_event_type_created_at", "job_id", "event_type", "created_at"),
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
    assigned_org_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organisations.id"),
        nullable=True,
    )
    assigned_contractor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("locations.id"),
        nullable=True,
        index=True,
    )
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("assets.id"),
        nullable=True,
        index=True,
    )
    event_type: Mapped[EventType] = mapped_column(
        Enum(
            EventType,
            name="event_type_enum",
            native_enum=False,
            validate_strings=True,
        ),
        nullable=False,
        default=EventType.note,
        server_default=EventType.note.value,
    )
    target_status: Mapped[JobStatus | None] = mapped_column(
        Enum(
            JobStatus,
            name="job_status_enum",
            native_enum=False,
            validate_strings=True,
        ),
        nullable=True,
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    reason_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    responsibility_stage: Mapped[ResponsibilityStage | None] = mapped_column(
        Enum(
            ResponsibilityStage,
            name="responsibility_stage_enum",
            native_enum=False,
            validate_strings=True,
        ),
        nullable=True,
    )
    owner_scope: Mapped[OwnerScope | None] = mapped_column(
        Enum(
            OwnerScope,
            name="owner_scope_enum",
            native_enum=False,
            validate_strings=True,
        ),
        nullable=True,
    )
    responsibility_owner: Mapped[ResponsibilityOwner | None] = mapped_column(
        Enum(
            ResponsibilityOwner,
            name="responsibility_owner_enum",
            native_enum=False,
            validate_strings=True,
        ),
        nullable=True,
    )
    created_at: Mapped[datetime] = created_timestamp()

    job: Mapped[Job] = relationship(back_populates="events")
    actor_user: Mapped[User | None] = relationship(
        back_populates="events",
        foreign_keys=[actor_user_id],
    )
    actor_org: Mapped[Organisation | None] = relationship(foreign_keys=[actor_org_id])
    assigned_org: Mapped[Organisation | None] = relationship(foreign_keys=[assigned_org_id])
    assigned_contractor: Mapped[User | None] = relationship(foreign_keys=[assigned_contractor_user_id])
    location_record: Mapped[Location | None] = relationship(
        back_populates="events",
        foreign_keys=[location_id],
    )
    asset: Mapped[Asset | None] = relationship(
        back_populates="events",
        foreign_keys=[asset_id],
    )
