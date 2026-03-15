from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, created_timestamp, uuid_pk
from app.models.enums import JobStatus

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.organisation import Organisation
    from app.models.user import User


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_created_by_created_at", "created_by", "created_at"),
        Index("ix_jobs_assigned_org_status", "assigned_org_id", "status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status_enum", native_enum=False, validate_strings=True),
        nullable=False,
        default=JobStatus.new,
        server_default=JobStatus.new.value,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    assigned_org_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organisations.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = created_timestamp()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    creator: Mapped[User] = relationship(
        back_populates="created_jobs",
        foreign_keys=[created_by],
    )
    assigned_org: Mapped[Organisation | None] = relationship(
        back_populates="assigned_jobs",
        foreign_keys=[assigned_org_id],
    )
    events: Mapped[list[Event]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="Event.created_at",
    )
