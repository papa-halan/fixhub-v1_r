from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, Text, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, created_timestamp, uuid_pk
from app.models.enums import UserRole

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.job import Job
    from app.models.organisation import Organisation


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role_enum", native_enum=False, validate_strings=True),
        nullable=False,
    )
    is_demo_account: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
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
    created_jobs: Mapped[list[Job]] = relationship(
        back_populates="creator",
        foreign_keys="Job.created_by",
    )
    reported_jobs: Mapped[list[Job]] = relationship(
        back_populates="reported_for_user",
        foreign_keys="Job.reported_for_user_id",
    )
    direct_assigned_jobs: Mapped[list[Job]] = relationship(
        back_populates="assigned_contractor",
        foreign_keys="Job.assigned_contractor_user_id",
    )
    events: Mapped[list[Event]] = relationship(
        back_populates="actor_user",
        foreign_keys="Event.actor_user_id",
    )
