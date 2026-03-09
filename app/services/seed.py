from __future__ import annotations
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Organisation, Residence, RoutingRule, Unit, User, UserRole
from app.services.passwords import hash_password


@dataclass(frozen=True)
class SeedData:
    org_id: uuid.UUID
    residence_id: uuid.UUID
    unit_id: uuid.UUID
    resident_user_id: uuid.UUID
    staff_user_id: uuid.UUID
    contractor_user_id: uuid.UUID
    override_contractor_user_id: uuid.UUID
    category: str


def _set_dev_password(user: User, password: str) -> None:
    user.password_hash = hash_password(password)


def ensure_seed_data(session: Session) -> SeedData:
    org = session.scalar(
        select(Organisation).where(Organisation.name == "UoN Student Living").limit(1)
    )
    if org is None:
        org = Organisation(name="UoN Student Living")
        session.add(org)
        session.flush()

    residence = session.scalar(
        select(Residence)
        .where(Residence.org_id == org.org_id)
        .where(Residence.name == "Trent House")
        .limit(1)
    )
    if residence is None:
        residence = Residence(org_id=org.org_id, name="Trent House")
        session.add(residence)
        session.flush()

    unit = session.scalar(
        select(Unit)
        .where(Unit.residence_id == residence.residence_id)
        .where(Unit.label == "Block A Room 14")
        .limit(1)
    )
    if unit is None:
        unit = Unit(residence_id=residence.residence_id, label="Block A Room 14")
        session.add(unit)
        session.flush()

    resident = session.scalar(
        select(User).where(User.email == "resident@uon.example").limit(1)
    )
    if resident is None:
        resident = User(
            org_id=org.org_id,
            email="resident@uon.example",
            password_hash=hash_password("resident-password"),
            role=UserRole.resident,
        )
        session.add(resident)
        session.flush()
    else:
        _set_dev_password(resident, "resident-password")
        resident.role = UserRole.resident

    staff = session.scalar(select(User).where(User.email == "staff@uon.example").limit(1))
    if staff is None:
        staff = User(
            org_id=org.org_id,
            email="staff@uon.example",
            password_hash=hash_password("staff-password"),
            role=UserRole.staff,
        )
        session.add(staff)
        session.flush()
    else:
        _set_dev_password(staff, "staff-password")
        staff.role = UserRole.staff

    contractor = session.scalar(
        select(User).where(User.email == "contractor@uon.example").limit(1)
    )
    if contractor is None:
        contractor = User(
            org_id=org.org_id,
            email="contractor@uon.example",
            password_hash=hash_password("contractor-password"),
            role=UserRole.contractor,
        )
        session.add(contractor)
        session.flush()
    else:
        _set_dev_password(contractor, "contractor-password")
        contractor.role = UserRole.contractor

    override_contractor = session.scalar(
        select(User).where(User.email == "contractor-override@uon.example").limit(1)
    )
    if override_contractor is None:
        override_contractor = User(
            org_id=org.org_id,
            email="contractor-override@uon.example",
            password_hash=hash_password("contractor-override-password"),
            role=UserRole.contractor,
        )
        session.add(override_contractor)
        session.flush()
    else:
        _set_dev_password(override_contractor, "contractor-override-password")
        override_contractor.role = UserRole.contractor

    category = "plumbing"
    routing_rule = session.scalar(
        select(RoutingRule)
        .where(RoutingRule.residence_id == residence.residence_id)
        .where(RoutingRule.category == category)
        .limit(1)
    )
    if routing_rule is None:
        routing_rule = RoutingRule(
            org_id=org.org_id,
            residence_id=residence.residence_id,
            category=category,
            contractor_user_id=contractor.user_id,
            enabled=True,
        )
        session.add(routing_rule)
        session.flush()
    else:
        routing_rule.contractor_user_id = contractor.user_id
        routing_rule.enabled = True

    return SeedData(
        org_id=org.org_id,
        residence_id=residence.residence_id,
        unit_id=unit.unit_id,
        resident_user_id=resident.user_id,
        staff_user_id=staff.user_id,
        contractor_user_id=contractor.user_id,
        override_contractor_user_id=override_contractor.user_id,
        category=category,
    )
