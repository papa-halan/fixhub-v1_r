from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Organisation, OrganisationType, User, UserRole


@dataclass(frozen=True)
class DemoUser:
    name: str
    email: str
    role: UserRole
    organisation_name: str | None = None
    organisation_type: OrganisationType | None = None


DEMO_USERS: tuple[DemoUser, ...] = (
    DemoUser(
        name="Riley Resident",
        email="resident@fixhub.test",
        role=UserRole.resident,
        organisation_name="Student Living",
        organisation_type=OrganisationType.university,
    ),
    DemoUser(
        name="Avery Admin",
        email="admin@fixhub.test",
        role=UserRole.admin,
        organisation_name="Student Living",
        organisation_type=OrganisationType.university,
    ),
    DemoUser(
        name="Devon Contractor",
        email="contractor@fixhub.test",
        role=UserRole.contractor,
        organisation_name="Newcastle Plumbing",
        organisation_type=OrganisationType.contractor,
    ),
)


def ensure_demo_data(session: Session) -> None:
    org_cache: dict[str, Organisation] = {}

    for demo in DEMO_USERS:
        organisation: Organisation | None = None
        if demo.organisation_name and demo.organisation_type:
            organisation = org_cache.get(demo.organisation_name)
            if organisation is None:
                organisation = session.scalar(
                    select(Organisation).where(Organisation.name == demo.organisation_name).limit(1)
                )
            if organisation is None:
                organisation = Organisation(
                    name=demo.organisation_name,
                    type=demo.organisation_type,
                )
                session.add(organisation)
                session.flush()
            else:
                organisation.type = demo.organisation_type
            org_cache[demo.organisation_name] = organisation

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
