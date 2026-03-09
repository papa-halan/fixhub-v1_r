from __future__ import annotations

import unittest
import uuid

from app.models import MaintenanceRequest, User, UserRole, WorkOrder, WorkOrderStatus
from app.services.policy import AccessDeniedError, AuthorisationPolicy


class UserSession:
    def __init__(self, users: dict[uuid.UUID, User]) -> None:
        self.users = users

    def get(self, model: type[User], user_id: uuid.UUID) -> User | None:
        assert model is User
        return self.users.get(user_id)


def make_user(
    *,
    user_id: uuid.UUID,
    role: UserRole,
    org_id: uuid.UUID | None = None,
    is_active: bool = True,
) -> User:
    return User(
        user_id=user_id,
        org_id=org_id,
        email=f"{role.value}-{user_id}@example.com",
        password_hash="hash",
        role=role,
        is_active=is_active,
    )


class AuthorisationPolicyTests(unittest.TestCase):
    def test_require_resident_rejects_inactive_users(self) -> None:
        resident_id = uuid.uuid4()
        org_id = uuid.uuid4()
        policy = AuthorisationPolicy(
            UserSession(
                {
                    resident_id: make_user(
                        user_id=resident_id,
                        role=UserRole.resident,
                        org_id=org_id,
                        is_active=False,
                    )
                }
            )
        )

        with self.assertRaisesRegex(AccessDeniedError, "inactive"):
            policy.require_resident(user_id=resident_id, org_id=org_id)

    def test_require_staff_rejects_wrong_org_assignment(self) -> None:
        staff_id = uuid.uuid4()
        assigned_org_id = uuid.uuid4()
        other_org_id = uuid.uuid4()
        policy = AuthorisationPolicy(
            UserSession(
                {
                    staff_id: make_user(
                        user_id=staff_id,
                        role=UserRole.staff,
                        org_id=assigned_org_id,
                    )
                }
            )
        )

        with self.assertRaisesRegex(AccessDeniedError, "not allowed to act in org"):
            policy.require_staff(user_id=staff_id, org_id=other_org_id)

    def test_resolve_staff_org_scope_requires_explicit_org_for_unscoped_staff(self) -> None:
        staff_id = uuid.uuid4()
        policy = AuthorisationPolicy(
            UserSession(
                {
                    staff_id: make_user(
                        user_id=staff_id,
                        role=UserRole.staff,
                        org_id=None,
                    )
                }
            )
        )

        with self.assertRaisesRegex(ValueError, "org_id is required"):
            policy.resolve_staff_org_scope(staff_user_id=staff_id)

    def test_require_request_owner_rejects_other_residents(self) -> None:
        owner_id = uuid.uuid4()
        other_resident_id = uuid.uuid4()
        org_id = uuid.uuid4()
        request = MaintenanceRequest(
            request_id=uuid.uuid4(),
            org_id=org_id,
            unit_id=uuid.uuid4(),
            resident_user_id=owner_id,
            category="plumbing",
            description="Tap is leaking",
        )
        policy = AuthorisationPolicy(
            UserSession(
                {
                    other_resident_id: make_user(
                        user_id=other_resident_id,
                        role=UserRole.resident,
                        org_id=org_id,
                    )
                }
            )
        )

        with self.assertRaisesRegex(AccessDeniedError, "not owned by resident"):
            policy.require_request_owner(
                request=request,
                resident_user_id=other_resident_id,
            )

    def test_require_assigned_contractor_rejects_unassigned_user(self) -> None:
        assigned_contractor_id = uuid.uuid4()
        other_contractor_id = uuid.uuid4()
        org_id = uuid.uuid4()
        work_order = WorkOrder(
            work_order_id=uuid.uuid4(),
            org_id=org_id,
            request_id=uuid.uuid4(),
            contractor_user_id=assigned_contractor_id,
            status=WorkOrderStatus.assigned,
        )
        policy = AuthorisationPolicy(
            UserSession(
                {
                    other_contractor_id: make_user(
                        user_id=other_contractor_id,
                        role=UserRole.contractor,
                        org_id=org_id,
                    )
                }
            )
        )

        with self.assertRaisesRegex(AccessDeniedError, "is not assigned to work_order"):
            policy.require_assigned_contractor(
                work_order=work_order,
                contractor_user_id=other_contractor_id,
            )
