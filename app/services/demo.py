from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Asset,
    ContractorMode,
    Location,
    LocationType,
    Organisation,
    OrganisationType,
    User,
    UserRole,
)
from app.services.passwords import hash_password, verify_password


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


@dataclass(frozen=True)
class DemoLocation:
    name: str
    organisation_name: str
    type: LocationType
    parent_name: str | None = None


@dataclass(frozen=True)
class DemoAsset:
    location_name: str
    name: str


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
    DemoOrganisation(
        name="Independent Contractors",
        type=OrganisationType.contractor,
        contractor_mode=ContractorMode.external_contractor,
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
        name="Sky System Admin",
        email="admin@fixhub.test",
        role=UserRole.admin,
        organisation_name="Student Living",
    ),
    DemoUser(
        name="Fran Front Desk",
        email="reception@fixhub.test",
        role=UserRole.reception_admin,
        organisation_name="Student Living",
    ),
    DemoUser(
        name="Priya Property Manager",
        email="triage@fixhub.test",
        role=UserRole.triage_officer,
        organisation_name="Student Living",
    ),
    DemoUser(
        name="Casey Dispatch Coordinator",
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
        name="Maddie Maintenance Technician",
        email="maintenance.contractor@fixhub.test",
        role=UserRole.contractor,
        organisation_name="Campus Maintenance",
    ),
    DemoUser(
        name="Indy Independent Contractor",
        email="independent.contractor@fixhub.test",
        role=UserRole.contractor,
        organisation_name="Independent Contractors",
    ),
)


DEMO_LOCATIONS: tuple[DemoLocation, ...] = (
    DemoLocation(
        name="Callaghan Campus",
        organisation_name="Student Living",
        type=LocationType.site,
    ),
    DemoLocation(
        name="Block A",
        organisation_name="Student Living",
        type=LocationType.building,
        parent_name="Callaghan Campus",
    ),
    DemoLocation(
        name="Block B",
        organisation_name="Student Living",
        type=LocationType.building,
        parent_name="Callaghan Campus",
    ),
    DemoLocation(
        name="Block C",
        organisation_name="Student Living",
        type=LocationType.building,
        parent_name="Callaghan Campus",
    ),
    DemoLocation(
        name="Block D",
        organisation_name="Student Living",
        type=LocationType.building,
        parent_name="Callaghan Campus",
    ),
    DemoLocation(
        name="Block E",
        organisation_name="Student Living",
        type=LocationType.building,
        parent_name="Callaghan Campus",
    ),
    DemoLocation(
        name="Block F",
        organisation_name="Student Living",
        type=LocationType.building,
        parent_name="Callaghan Campus",
    ),
    DemoLocation(
        name="Block G",
        organisation_name="Student Living",
        type=LocationType.building,
        parent_name="Callaghan Campus",
    ),
    DemoLocation(
        name="Block H",
        organisation_name="Student Living",
        type=LocationType.building,
        parent_name="Callaghan Campus",
    ),
    DemoLocation(
        name="Block J",
        organisation_name="Student Living",
        type=LocationType.building,
        parent_name="Callaghan Campus",
    ),
    DemoLocation(
        name="Block K",
        organisation_name="Student Living",
        type=LocationType.building,
        parent_name="Callaghan Campus",
    ),
    DemoLocation(
        name="Block L",
        organisation_name="Student Living",
        type=LocationType.building,
        parent_name="Callaghan Campus",
    ),
    DemoLocation(
        name="Block A Room 14",
        organisation_name="Student Living",
        type=LocationType.unit,
        parent_name="Block A",
    ),
    DemoLocation(
        name="Block B Room 8",
        organisation_name="Student Living",
        type=LocationType.unit,
        parent_name="Block B",
    ),
    DemoLocation(
        name="Block A Common Room",
        organisation_name="Student Living",
        type=LocationType.space,
        parent_name="Block A",
    ),
    DemoLocation(
        name="Block B Laundry",
        organisation_name="Student Living",
        type=LocationType.space,
        parent_name="Block B",
    ),
    DemoLocation(
        name="Block C Room 5",
        organisation_name="Student Living",
        type=LocationType.unit,
        parent_name="Block C",
    ),
    DemoLocation(
        name="Block D Room 12",
        organisation_name="Student Living",
        type=LocationType.unit,
        parent_name="Block D",
    ),
    DemoLocation(
        name="Block E Kitchen",
        organisation_name="Student Living",
        type=LocationType.space,
        parent_name="Block E",
    ),
    DemoLocation(
        name="Block F Room 3",
        organisation_name="Student Living",
        type=LocationType.unit,
        parent_name="Block F",
    ),
    DemoLocation(
        name="Block G Room 9",
        organisation_name="Student Living",
        type=LocationType.unit,
        parent_name="Block G",
    ),
    DemoLocation(
        name="Block H Room 2",
        organisation_name="Student Living",
        type=LocationType.unit,
        parent_name="Block H",
    ),
    DemoLocation(
        name="Block J Lounge",
        organisation_name="Student Living",
        type=LocationType.space,
        parent_name="Block J",
    ),
    DemoLocation(
        name="Block K Laundry",
        organisation_name="Student Living",
        type=LocationType.space,
        parent_name="Block K",
    ),
    DemoLocation(
        name="Block L Room 7",
        organisation_name="Student Living",
        type=LocationType.unit,
        parent_name="Block L",
    ),
)


DEMO_ASSETS: tuple[DemoAsset, ...] = (
    DemoAsset(location_name="Block A Room 14", name="Sink"),
    DemoAsset(location_name="Block A Room 14", name="Tap"),
    DemoAsset(location_name="Block A Room 14", name="Wardrobe Hinge"),
    DemoAsset(location_name="Block B Room 8", name="Door Closer"),
    DemoAsset(location_name="Block B Room 8", name="Bathroom Fan"),
    DemoAsset(location_name="Block A Common Room", name="Heater"),
    DemoAsset(location_name="Block B Laundry", name="Pump"),
)


DEMO_USER_EMAILS = {demo.email for demo in DEMO_USERS}


def ensure_demo_data(session: Session, *, demo_password: str) -> None:
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
        if user.password_hash is None or not verify_password(demo_password, user.password_hash):
            user.password_hash = hash_password(demo_password)
        user.is_demo_account = True

    session.flush()

    location_cache: dict[str, Location] = {}
    for demo_location in DEMO_LOCATIONS:
        organisation = org_cache[demo_location.organisation_name]
        location = session.scalar(
            select(Location)
            .where(
                Location.organisation_id == organisation.id,
                Location.name == demo_location.name,
            )
            .limit(1)
        )
        if location is None:
            location = Location(
                organisation_id=organisation.id,
                name=demo_location.name,
                type=demo_location.type,
            )
            session.add(location)
            session.flush()
        else:
            location.type = demo_location.type
        location_cache[demo_location.name] = location

    for demo_location in DEMO_LOCATIONS:
        location = location_cache[demo_location.name]
        location.parent_id = location_cache[demo_location.parent_name].id if demo_location.parent_name else None

    session.flush()

    for demo_asset in DEMO_ASSETS:
        location = location_cache[demo_asset.location_name]
        asset = session.scalar(
            select(Asset)
            .where(Asset.location_id == location.id, Asset.name == demo_asset.name)
            .limit(1)
        )
        if asset is None:
            session.add(Asset(location_id=location.id, name=demo_asset.name))

    session.flush()


def list_demo_users(session: Session) -> Sequence[User]:
    emails = [demo.email for demo in DEMO_USERS]
    users = list(session.scalars(select(User).where(User.is_demo_account.is_(True))))
    order = {email: index for index, email in enumerate(emails)}
    users.sort(key=lambda user: (order.get(user.email, len(order)), user.name))
    return users


def is_demo_user_email(email: str) -> bool:
    return email in DEMO_USER_EMAILS
