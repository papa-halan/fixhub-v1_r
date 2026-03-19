from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ContractorMode, Organisation, OrganisationType, User, UserRole


@dataclass(frozen=True)
class DemoOrganisation:
    name: str
    type: OrganisationType
    parent_name: str | None = None
    contractor_mode: ContractorMode | None = None


@dataclass(frozen=True)
class DemoUser:
    name: str
    email: str
    role: UserRole
    organisation_name: str | None = None


DEMO_ORGANISATIONS: tuple[DemoOrganisation, ...] = (
    DemoOrganisation(
        name="University of Newcastle",
        type=OrganisationType.university,
    ),
    DemoOrganisation(
        name="Student Living",
        type=OrganisationType.university,
        parent_name="University of Newcastle",
    ),
    DemoOrganisation(
        name="Newcastle Plumbing",
        type=OrganisationType.contractor,
        contractor_mode=ContractorMode.external_contractor,
    ),
    DemoOrganisation(
        name="Campus Maintenance",
        type=OrganisationType.contractor,
        contractor_mode=ContractorMode.maintenance_team,
    ),
)


DEMO_USERS: tuple[DemoUser, ...] = (
    DemoUser(
        name="Riley Resident",
        email="resident@fixhub.test",
        role=UserRole.resident,
        organisation_name="Student Living",
    ),
    DemoUser(
        name="Avery Admin",
        email="admin@fixhub.test",
        role=UserRole.admin,
        organisation_name="Student Living",
    ),
    DemoUser(
        name="Remy Reception",
        email="reception@fixhub.test",
        role=UserRole.reception_admin,
        organisation_name="Student Living",
    ),
    DemoUser(
        name="Taylor Triage",
        email="triage@fixhub.test",
        role=UserRole.triage_officer,
        organisation_name="Student Living",
    ),
    DemoUser(
        name="Cory Coordinator",
        email="coordinator@fixhub.test",
        role=UserRole.coordinator,
        organisation_name="Student Living",
    ),
    DemoUser(
        name="Devon Contractor",
        email="contractor@fixhub.test",
        role=UserRole.contractor,
        organisation_name="Newcastle Plumbing",
    ),
    DemoUser(
        name="Maddie Maintenance",
        email="maintenance.contractor@fixhub.test",
        role=UserRole.contractor,
        organisation_name="Campus Maintenance",
    ),
    DemoUser(
        name="Indy Independent",
        email="independent.contractor@fixhub.test",
        role=UserRole.contractor,
    ),
)


def ensure_demo_data(session: Session) -> None:
    org_cache: dict[str, Organisation] = {}

    for demo_org in DEMO_ORGANISATIONS:
        organisation = org_cache.get(demo_org.name)
        if organisation is None:
            organisation = session.scalar(
                select(Organisation).where(Organisation.name == demo_org.name).limit(1)
            )
        if organisation is None:
            organisation = Organisation(name=demo_org.name, type=demo_org.type)
            session.add(organisation)
            session.flush()
        organisation.type = demo_org.type
        organisation.contractor_mode = demo_org.contractor_mode
        org_cache[demo_org.name] = organisation

    for demo_org in DEMO_ORGANISATIONS:
        organisation = org_cache[demo_org.name]
        organisation.parent_org_id = (
            org_cache[demo_org.parent_name].id if demo_org.parent_name is not None else None
        )

    for demo in DEMO_USERS:
        organisation = org_cache.get(demo.organisation_name) if demo.organisation_name else None

        user = session.scalar(select(User).where(User.email == demo.email).limit(1))
        if user is None:
            user = User(
                name=demo.name,
                email=demo.email,
                role=demo.role,
                organisation_id=organisation.id if organisation else None,
            )
            session.add(user)
        else:
            user.name = demo.name
            user.role = demo.role
            user.organisation_id = organisation.id if organisation else None

    session.flush()


def list_demo_users(session: Session) -> Sequence[User]:
    emails = [demo.email for demo in DEMO_USERS]
    users = list(session.scalars(select(User).where(User.email.in_(emails))))
    order = {email: index for index, email in enumerate(emails)}
    users.sort(key=lambda user: order[user.email])
    return users
