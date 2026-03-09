from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models import MaintenanceRequest, User, UserRole, WorkOrder


class AccessDeniedError(PermissionError):
    pass


class AuthorisationPolicy:
    def __init__(self, session: Session) -> None:
        self.session = session

    def require_resident(
        self,
        *,
        user_id: uuid.UUID,
        org_id: uuid.UUID | None = None,
    ) -> User:
        return self._require_active_user(
            user_id=user_id,
            expected_role=UserRole.resident,
            org_id=org_id,
        )

    def require_staff(
        self,
        *,
        user_id: uuid.UUID,
        org_id: uuid.UUID | None = None,
    ) -> User:
        return self._require_active_user(
            user_id=user_id,
            expected_role=UserRole.staff,
            org_id=org_id,
        )

    def require_contractor(
        self,
        *,
        user_id: uuid.UUID,
        org_id: uuid.UUID | None = None,
    ) -> User:
        return self._require_active_user(
            user_id=user_id,
            expected_role=UserRole.contractor,
            org_id=org_id,
        )

    def require_request_owner(
        self,
        *,
        request: MaintenanceRequest,
        resident_user_id: uuid.UUID,
    ) -> User:
        resident = self.require_resident(user_id=resident_user_id, org_id=request.org_id)
        if request.resident_user_id != resident.user_id:
            raise AccessDeniedError(
                f"MaintenanceRequest {request.request_id} is not owned by resident {resident_user_id}"
            )
        return resident

    def resolve_staff_org_scope(
        self,
        *,
        staff_user_id: uuid.UUID,
        requested_org_id: uuid.UUID | None = None,
    ) -> uuid.UUID:
        staff = self.require_staff(user_id=staff_user_id)
        resolved_org_id = requested_org_id if requested_org_id is not None else staff.org_id
        if resolved_org_id is None:
            raise ValueError("org_id is required when staff user has no org assignment")
        if staff.org_id not in (None, resolved_org_id):
            raise AccessDeniedError(
                f"Staff user {staff_user_id} cannot act in org {resolved_org_id}"
            )
        return resolved_org_id

    def require_assigned_contractor(
        self,
        *,
        work_order: WorkOrder,
        contractor_user_id: uuid.UUID,
    ) -> User:
        contractor = self.require_contractor(
            user_id=contractor_user_id,
            org_id=work_order.org_id,
        )
        if work_order.contractor_user_id != contractor.user_id:
            raise AccessDeniedError(
                f"Contractor {contractor_user_id} is not assigned to work_order {work_order.work_order_id}"
            )
        return contractor

    def _require_active_user(
        self,
        *,
        user_id: uuid.UUID,
        expected_role: UserRole,
        org_id: uuid.UUID | None = None,
    ) -> User:
        user = self.session.get(User, user_id)
        if user is None:
            raise ValueError(f"User {user_id} does not exist")
        if not user.is_active:
            raise AccessDeniedError(f"User {user_id} is inactive")
        if user.role != expected_role:
            raise AccessDeniedError(
                f"User {user_id} has role={user.role.value}, expected={expected_role.value}"
            )
        if org_id is not None and user.org_id not in (None, org_id):
            raise AccessDeniedError(f"User {user_id} is not allowed to act in org {org_id}")
        return user
