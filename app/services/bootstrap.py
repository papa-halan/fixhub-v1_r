from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Organisation, OrganisationType, User, UserRole
from app.services.passwords import hash_password, verify_password


def ensure_bootstrap_user(
    session: Session,
    *,
    name: str,
    email: str | None,
    password: str | None,
    organisation_name: str,
    role: UserRole,
) -> User | None:
    if not email or not password:
        return None

    organisation_type = OrganisationType.contractor if role == UserRole.contractor else OrganisationType.university
    organisation = session.scalar(select(Organisation).where(Organisation.name == organisation_name).limit(1))
    if organisation is None:
        organisation = Organisation(name=organisation_name, type=organisation_type)
        session.add(organisation)
        session.flush()
    else:
        organisation.type = organisation_type

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
    user.is_demo_account = False
    session.flush()
    return user
