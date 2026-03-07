from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Organisation, Residence, RoutingRule, Unit, User, UserRole


@dataclass(frozen=True)
class SeedData:
    org_id: uuid.UUID
    residence_id: uuid.UUID
    unit_id: uuid.UUID
    resident_user_id: uuid.UUID
    contractor_user_id: uuid.UUID
    category: str


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
            password_hash="resident-hash",
            role=UserRole.resident,
        )
        session.add(resident)
        session.flush()

    contractor = session.scalar(
        select(User).where(User.email == "contractor@uon.example").limit(1)
    )
    if contractor is None:
        contractor = User(
            org_id=org.org_id,
            email="contractor@uon.example",
            password_hash="contractor-hash",
            role=UserRole.contractor,
        )
        session.add(contractor)
        session.flush()

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
        contractor_user_id=contractor.user_id,
        category=category,
    )