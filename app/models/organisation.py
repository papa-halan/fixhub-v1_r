from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, created_timestamp, uuid_pk
from app.models.enums import ContractorMode, OrganisationType

if TYPE_CHECKING:
    from app.models.job import Job
    from app.models.location import Location
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
    parent_org_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organisations.id"),
        nullable=True,
        index=True,
    )
    contractor_mode: Mapped[ContractorMode | None] = mapped_column(
        Enum(
            ContractorMode,
            name="contractor_mode_enum",
            native_enum=False,
            validate_strings=True,
        ),
        nullable=True,
    )
    created_at: Mapped[datetime] = created_timestamp()

    parent_org: Mapped[Organisation | None] = relationship(
        remote_side="Organisation.id",
        back_populates="child_orgs",
    )
    child_orgs: Mapped[list[Organisation]] = relationship(
        back_populates="parent_org",
        order_by="Organisation.name",
    )
    users: Mapped[list[User]] = relationship(back_populates="organisation")
    locations: Mapped[list[Location]] = relationship(
        back_populates="organisation",
        order_by="Location.name",
    )
    jobs: Mapped[list[Job]] = relationship(
        back_populates="organisation",
        foreign_keys="Job.organisation_id",
    )
    assigned_jobs: Mapped[list[Job]] = relationship(
        back_populates="assigned_org",
        foreign_keys="Job.assigned_org_id",
    )
