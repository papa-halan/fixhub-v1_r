from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Enum, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, created_timestamp, uuid_pk
from app.models.enums import OrganisationType

if TYPE_CHECKING:
    from app.models.job import Job
    from app.models.user import User


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

    users: Mapped[list[User]] = relationship(back_populates="organisation")
    assigned_jobs: Mapped[list[Job]] = relationship(
        back_populates="assigned_org",
        foreign_keys="Job.assigned_org_id",
    )
