from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Asset, Location, LocationType, Organisation, OrganisationType, User, UserRole
from app.services.catalog import location_label
from app.services.passwords import hash_password, verify_password


@dataclass(frozen=True)
class MinimalSeedConfig:
    organisation_name: str = "Student Living"
    site_name: str = "Callaghan Campus"
    building_name: str = "Block A"
    unit_name: str = "Block A Room 14"
    shared_space_name: str | None = "Block A Common Room"
    asset_name: str | None = "Sink"
    operator_name: str = "FixHub Admin"
    operator_email: str = "ops@fixhub.local"
    operator_password: str = "fixhub-admin-password"
    operator_role: UserRole = UserRole.admin
    resident_name: str = "Test Resident"
    resident_email: str = "resident@fixhub.local"
    resident_password: str = "fixhub-resident-password"


@dataclass(frozen=True)
class MinimalSeedSummary:
    organisation_id: uuid.UUID
    site_id: uuid.UUID
    building_id: uuid.UUID
    unit_id: uuid.UUID
    unit_label: str
    shared_space_id: uuid.UUID | None
    shared_space_label: str | None
    asset_id: uuid.UUID | None
    asset_name: str | None
    operator_user_id: uuid.UUID
    operator_email: str
    operator_role: UserRole
    resident_user_id: uuid.UUID
    resident_email: str


def _ensure_organisation(
    session: Session,
    *,
    name: str,
    organisation_type: OrganisationType,
) -> Organisation:
    organisation = session.scalar(select(Organisation).where(Organisation.name == name).limit(1))
    if organisation is None:
        organisation = Organisation(name=name, type=organisation_type)
        session.add(organisation)
        session.flush()
    else:
        organisation.type = organisation_type
    return organisation


def _ensure_location(
    session: Session,
    *,
    organisation: Organisation,
    name: str,
    location_type: LocationType,
    parent: Location | None,
) -> Location:
    location = session.scalar(
        select(Location)
        .where(
            Location.organisation_id == organisation.id,
            Location.name == name,
        )
        .limit(1)
    )
    if location is None:
        location = Location(
            organisation_id=organisation.id,
            name=name,
            type=location_type,
            parent_id=parent.id if parent is not None else None,
        )
        session.add(location)
        session.flush()
    else:
        location.type = location_type
        location.parent_id = parent.id if parent is not None else None
    return location


def _ensure_user(
    session: Session,
    *,
    organisation: Organisation,
    name: str,
    email: str,
    password: str,
    role: UserRole,
    home_location: Location | None = None,
) -> User:
    user = session.scalar(select(User).where(User.email == email).limit(1))
    if user is None:
        user = User(
            name=name,
            email=email,
            role=role,
            organisation_id=organisation.id,
        )
        session.add(user)
    else:
        user.name = name
        user.role = role
        user.organisation_id = organisation.id

    if user.password_hash is None or not verify_password(password, user.password_hash):
        user.password_hash = hash_password(password)
    user.home_location_id = home_location.id if home_location is not None else None
    user.is_demo_account = False
    session.flush()
    return user


def _ensure_asset(
    session: Session,
    *,
    location: Location,
    name: str,
) -> Asset:
    asset = session.scalar(
        select(Asset)
        .where(
            Asset.location_id == location.id,
            Asset.name == name,
        )
        .limit(1)
    )
    if asset is None:
        asset = Asset(location_id=location.id, name=name)
        session.add(asset)
        session.flush()
    return asset


def ensure_minimal_seed_data(
    session: Session,
    *,
    config: MinimalSeedConfig,
) -> MinimalSeedSummary:
    if config.operator_role not in {
        UserRole.admin,
        UserRole.reception_admin,
        UserRole.triage_officer,
        UserRole.coordinator,
    }:
        raise ValueError("operator_role must be an operations role")

    organisation = _ensure_organisation(
        session,
        name=config.organisation_name,
        organisation_type=OrganisationType.university,
    )
    site = _ensure_location(
        session,
        organisation=organisation,
        name=config.site_name,
        location_type=LocationType.site,
        parent=None,
    )
    building = _ensure_location(
        session,
        organisation=organisation,
        name=config.building_name,
        location_type=LocationType.building,
        parent=site,
    )
    unit = _ensure_location(
        session,
        organisation=organisation,
        name=config.unit_name,
        location_type=LocationType.unit,
        parent=building,
    )
    shared_space = (
        _ensure_location(
            session,
            organisation=organisation,
            name=config.shared_space_name,
            location_type=LocationType.space,
            parent=building,
        )
        if config.shared_space_name is not None
        else None
    )

    operator = _ensure_user(
        session,
        organisation=organisation,
        name=config.operator_name,
        email=config.operator_email,
        password=config.operator_password,
        role=config.operator_role,
    )
    resident = _ensure_user(
        session,
        organisation=organisation,
        name=config.resident_name,
        email=config.resident_email,
        password=config.resident_password,
        role=UserRole.resident,
        home_location=unit,
    )

    asset = _ensure_asset(session, location=unit, name=config.asset_name) if config.asset_name else None
    session.flush()

    return MinimalSeedSummary(
        organisation_id=organisation.id,
        site_id=site.id,
        building_id=building.id,
        unit_id=unit.id,
        unit_label=location_label(unit),
        shared_space_id=shared_space.id if shared_space is not None else None,
        shared_space_label=location_label(shared_space) if shared_space is not None else None,
        asset_id=asset.id if asset is not None else None,
        asset_name=asset.name if asset is not None else None,
        operator_user_id=operator.id,
        operator_email=operator.email,
        operator_role=operator.role,
        resident_user_id=resident.id,
        resident_email=resident.email,
    )
