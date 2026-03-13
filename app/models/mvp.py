from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, created_timestamp, uuid_pk
from app.models.enums import JobStatus, OrganisationType, UserRole


class Organisation(Base):
    __tablename__ = "organisations"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    type: Mapped[OrganisationType] = mapped_column(
        Enum(
            OrganisationType,
            name="organisation_type_enum",
            native_enum=False,
            validate_strings=True,
        ),
        nullable=False,
    )
    created_at: Mapped[datetime] = created_timestamp()

    users: Mapped[list["User"]] = relationship(back_populates="organisation")
    assigned_jobs: Mapped[list["Job"]] = relationship(
        back_populates="assigned_org",
        foreign_keys="Job.assigned_org_id",
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role_enum", native_enum=False, validate_strings=True),
        nullable=False,
    )
    organisation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organisations.id"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = created_timestamp()

    organisation: Mapped[Organisation | None] = relationship(
        back_populates="users",
        foreign_keys=[organisation_id],
    )
    created_jobs: Mapped[list["Job"]] = relationship(
        back_populates="creator",
        foreign_keys="Job.created_by",
    )
    events: Mapped[list["Event"]] = relationship(
        back_populates="actor_user",
        foreign_keys="Event.actor_user_id",
    )


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
    events: Mapped[list["Event"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="Event.created_at",
    )


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (Index("ix_events_job_created_at", "job_id", "created_at"),)

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
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = created_timestamp()

    job: Mapped[Job] = relationship(back_populates="events")
    actor_user: Mapped[User | None] = relationship(
        back_populates="events",
        foreign_keys=[actor_user_id],
    )
    actor_org: Mapped[Organisation | None] = relationship(foreign_keys=[actor_org_id])
