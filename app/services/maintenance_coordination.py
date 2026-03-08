from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    AuditEntry,
    DomainEvent,
    EVENT_INTEGRATION_COMPLETED,
    EVENT_INTEGRATION_FAILED,
    EVENT_INTEGRATION_REQUESTED,
    EVENT_MAINTENANCE_REQUEST_SUBMITTED,
    EVENT_WORK_ORDER_CREATED,
    EVENT_WORK_ORDER_STATUS_CHANGED,
    IntegrationJob,
    IntegrationJobStatus,
    MaintenanceRequest,
    Unit,
    User,
    UserRole,
    WorkOrder,
    WorkOrderStatus,
)
from app.services.routing import lookup_contractor_user_id


class AccessDeniedError(PermissionError):
    pass


class InvalidWorkOrderTransitionError(ValueError):
    pass


_ALLOWED_TRANSITIONS: dict[WorkOrderStatus, set[WorkOrderStatus]] = {
    WorkOrderStatus.assigned: {WorkOrderStatus.in_progress},
    WorkOrderStatus.in_progress: {WorkOrderStatus.completed},
    WorkOrderStatus.completed: set(),
}


def build_routing_key(org_id: uuid.UUID, residence_id: uuid.UUID, category: str) -> str:
    return f"org.{org_id}.residence.{residence_id}.category.{category}"


@dataclass(frozen=True)
class ResidentRequestStatus:
    request: MaintenanceRequest
    work_order: WorkOrder | None


class MaintenanceCoordinationService:
    def __init__(self, session: Session, source: str = settings.event_source) -> None:
        self.session = session
        self.source = source

    def _get_active_user(
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

    def _get_residence_id_for_unit(self, unit_id: uuid.UUID) -> uuid.UUID:
        residence_id = self.session.scalar(
            select(Unit.residence_id).where(Unit.unit_id == unit_id).limit(1)
        )
        if residence_id is None:
            raise ValueError(f"Unit {unit_id} does not exist")
        return residence_id

    def _append_event(
        self,
        *,
        event_type: str,
        subject_id: uuid.UUID,
        partition_key: str,
        routing_key: str,
        actor_user_id: uuid.UUID | None,
        data: dict[str, object] | None = None,
    ) -> DomainEvent:
        event = DomainEvent(
            type=event_type,
            source=self.source,
            subject_id=subject_id,
            partition_key=partition_key,
            routing_key=routing_key,
            actor_user_id=actor_user_id,
            data=data or {},
        )
        self.session.add(event)
        self.session.flush()
        self.session.add(AuditEntry(event_id=event.event_id))
        return event

    def _request_integration_job(
        self,
        *,
        work_order_id: uuid.UUID,
        routing_key: str,
        actor_user_id: uuid.UUID | None,
        connector: str,
        data: dict[str, object] | None = None,
    ) -> IntegrationJob:
        job_id = uuid.uuid4()
        event = self._append_event(
            event_type=EVENT_INTEGRATION_REQUESTED,
            subject_id=job_id,
            partition_key=str(work_order_id),
            routing_key=routing_key,
            actor_user_id=actor_user_id,
            data={
                "job_id": str(job_id),
                "connector": connector,
                "status": IntegrationJobStatus.requested.value,
                **(data or {}),
            },
        )
        integration_job = IntegrationJob(
            job_id=job_id,
            event_id=event.event_id,
            work_order_id=work_order_id,
            connector=connector,
            status=IntegrationJobStatus.requested,
            attempts=0,
        )
        self.session.add(integration_job)
        self.session.flush()
        return integration_job

    def submit_maintenance_request(
        self,
        *,
        org_id: uuid.UUID,
        unit_id: uuid.UUID,
        resident_user_id: uuid.UUID,
        category: str,
        description: str,
        priority: str | None = None,
    ) -> MaintenanceRequest:
        self._get_active_user(
            user_id=resident_user_id,
            expected_role=UserRole.resident,
            org_id=org_id,
        )
        residence_id = self._get_residence_id_for_unit(unit_id)

        request = MaintenanceRequest(
            org_id=org_id,
            unit_id=unit_id,
            resident_user_id=resident_user_id,
            category=category,
            priority=priority,
            description=description,
        )
        self.session.add(request)
        self.session.flush()

        self._append_event(
            event_type=EVENT_MAINTENANCE_REQUEST_SUBMITTED,
            subject_id=request.request_id,
            partition_key=str(org_id),
            routing_key=build_routing_key(org_id, residence_id, category),
            actor_user_id=resident_user_id,
            data={
                "request_id": str(request.request_id),
                "category": category,
            },
        )
        return request

    def get_resident_request_status(
        self,
        *,
        resident_user_id: uuid.UUID,
        request_id: uuid.UUID,
    ) -> ResidentRequestStatus:
        self._get_active_user(user_id=resident_user_id, expected_role=UserRole.resident)
        request = self.session.get(MaintenanceRequest, request_id)
        if request is None:
            raise ValueError(f"MaintenanceRequest {request_id} does not exist")
        if request.resident_user_id != resident_user_id:
            raise AccessDeniedError(
                f"MaintenanceRequest {request_id} is not owned by resident {resident_user_id}"
            )

        work_order = self.session.scalar(
            select(WorkOrder).where(WorkOrder.request_id == request_id).limit(1)
        )
        return ResidentRequestStatus(request=request, work_order=work_order)

    def list_submitted_requests_without_work_order(
        self,
        *,
        staff_user_id: uuid.UUID,
        org_id: uuid.UUID | None = None,
    ) -> list[MaintenanceRequest]:
        staff = self._get_active_user(user_id=staff_user_id, expected_role=UserRole.staff)
        resolved_org_id = org_id if org_id is not None else staff.org_id
        if resolved_org_id is None:
            raise ValueError("org_id is required when staff user has no org assignment")
        if staff.org_id not in (None, resolved_org_id):
            raise AccessDeniedError(
                f"Staff user {staff_user_id} cannot list requests for org {resolved_org_id}"
            )

        return list(
            self.session.scalars(
                select(MaintenanceRequest)
                .outerjoin(
                    WorkOrder,
                    WorkOrder.request_id == MaintenanceRequest.request_id,
                )
                .where(MaintenanceRequest.org_id == resolved_org_id)
                .where(WorkOrder.work_order_id.is_(None))
                .order_by(MaintenanceRequest.created_at.asc())
            )
        )

    def dispatch_request_to_work_order(
        self,
        *,
        request_id: uuid.UUID,
        staff_user_id: uuid.UUID,
        contractor_user_id_override: uuid.UUID | None = None,
        connector: str = "notify_contractor",
    ) -> tuple[WorkOrder, IntegrationJob]:
        request = self.session.get(MaintenanceRequest, request_id)
        if request is None:
            raise ValueError(f"MaintenanceRequest {request_id} does not exist")

        self._get_active_user(
            user_id=staff_user_id,
            expected_role=UserRole.staff,
            org_id=request.org_id,
        )

        existing_work_order_id = self.session.scalar(
            select(WorkOrder.work_order_id).where(WorkOrder.request_id == request_id).limit(1)
        )
        if existing_work_order_id is not None:
            raise ValueError(
                f"WorkOrder already exists for request_id={request_id}: {existing_work_order_id}"
            )

        residence_id = self._get_residence_id_for_unit(request.unit_id)
        if contractor_user_id_override is not None:
            contractor_user = self._get_active_user(
                user_id=contractor_user_id_override,
                expected_role=UserRole.contractor,
                org_id=request.org_id,
            )
            contractor_user_id = contractor_user.user_id
            dispatch_mode = "override"
        else:
            contractor_user_id = lookup_contractor_user_id(
                self.session,
                residence_id=residence_id,
                category=request.category,
            )
            self._get_active_user(
                user_id=contractor_user_id,
                expected_role=UserRole.contractor,
                org_id=request.org_id,
            )
            dispatch_mode = "routing_rule"

        work_order = WorkOrder(
            org_id=request.org_id,
            request_id=request.request_id,
            contractor_user_id=contractor_user_id,
            status=WorkOrderStatus.assigned,
        )
        self.session.add(work_order)
        self.session.flush()

        routing_key = build_routing_key(request.org_id, residence_id, request.category)
        self._append_event(
            event_type=EVENT_WORK_ORDER_CREATED,
            subject_id=work_order.work_order_id,
            partition_key=str(work_order.work_order_id),
            routing_key=routing_key,
            actor_user_id=staff_user_id,
            data={
                "request_id": str(request.request_id),
                "contractor_user_id": str(contractor_user_id),
                "status": work_order.status.value,
                "dispatch_mode": dispatch_mode,
            },
        )

        integration_job = self._request_integration_job(
            work_order_id=work_order.work_order_id,
            routing_key=routing_key,
            actor_user_id=staff_user_id,
            connector=connector,
            data={"request_id": str(request.request_id)},
        )
        return work_order, integration_job

    def _normalize_statuses(
        self,
        statuses: Iterable[WorkOrderStatus | str] | None,
    ) -> list[WorkOrderStatus]:
        if statuses is None:
            return []
        normalized: list[WorkOrderStatus] = []
        for status in statuses:
            normalized.append(status if isinstance(status, WorkOrderStatus) else WorkOrderStatus(status))
        return normalized

    def list_assigned_work_orders(
        self,
        *,
        contractor_user_id: uuid.UUID,
        statuses: Iterable[WorkOrderStatus | str] | None = None,
    ) -> list[WorkOrder]:
        self._get_active_user(user_id=contractor_user_id, expected_role=UserRole.contractor)
        normalized_statuses = self._normalize_statuses(statuses)
        stmt = (
            select(WorkOrder)
            .where(WorkOrder.contractor_user_id == contractor_user_id)
            .order_by(WorkOrder.created_at.asc())
        )
        if normalized_statuses:
            stmt = stmt.where(WorkOrder.status.in_(normalized_statuses))
        return list(self.session.scalars(stmt))

    def _transition_for_contractor(
        self,
        *,
        work_order_id: uuid.UUID,
        contractor_user_id: uuid.UUID,
        to_status: WorkOrderStatus,
        completion_note: str | None = None,
    ) -> WorkOrder:
        work_order = self.session.get(WorkOrder, work_order_id)
        if work_order is None:
            raise ValueError(f"WorkOrder {work_order_id} does not exist")
        self._get_active_user(
            user_id=contractor_user_id,
            expected_role=UserRole.contractor,
            org_id=work_order.org_id,
        )
        if work_order.contractor_user_id != contractor_user_id:
            raise AccessDeniedError(
                f"Contractor {contractor_user_id} is not assigned to work_order {work_order_id}"
            )

        allowed_next = _ALLOWED_TRANSITIONS[work_order.status]
        if to_status not in allowed_next:
            raise InvalidWorkOrderTransitionError(
                f"Invalid transition {work_order.status.value} -> {to_status.value}"
            )

        previous_status = work_order.status
        now = datetime.now(timezone.utc)
        work_order.status = to_status
        work_order.updated_at = now
        if to_status == WorkOrderStatus.completed:
            work_order.completed_at = now
        self.session.flush()

        request = self.session.get(MaintenanceRequest, work_order.request_id)
        if request is None:
            raise ValueError(f"MaintenanceRequest {work_order.request_id} does not exist")

        residence_id = self._get_residence_id_for_unit(request.unit_id)
        event_data: dict[str, object] = {
            "from": previous_status.value,
            "to": to_status.value,
        }
        if completion_note is not None:
            event_data["completion_note"] = completion_note

        self._append_event(
            event_type=EVENT_WORK_ORDER_STATUS_CHANGED,
            subject_id=work_order.work_order_id,
            partition_key=str(work_order.work_order_id),
            routing_key=build_routing_key(work_order.org_id, residence_id, request.category),
            actor_user_id=contractor_user_id,
            data=event_data,
        )
        return work_order

    def contractor_start_job(
        self,
        *,
        work_order_id: uuid.UUID,
        contractor_user_id: uuid.UUID,
    ) -> WorkOrder:
        return self._transition_for_contractor(
            work_order_id=work_order_id,
            contractor_user_id=contractor_user_id,
            to_status=WorkOrderStatus.in_progress,
        )

    def contractor_complete_job(
        self,
        *,
        work_order_id: uuid.UUID,
        contractor_user_id: uuid.UUID,
        completion_note: str | None = None,
        create_resident_notification_job: bool = False,
        connector: str = "notify_resident",
    ) -> tuple[WorkOrder, IntegrationJob | None]:
        work_order = self._transition_for_contractor(
            work_order_id=work_order_id,
            contractor_user_id=contractor_user_id,
            to_status=WorkOrderStatus.completed,
            completion_note=completion_note,
        )

        integration_job: IntegrationJob | None = None
        if create_resident_notification_job:
            request = self.session.get(MaintenanceRequest, work_order.request_id)
            if request is None:
                raise ValueError(f"MaintenanceRequest {work_order.request_id} does not exist")
            residence_id = self._get_residence_id_for_unit(request.unit_id)
            integration_job = self._request_integration_job(
                work_order_id=work_order.work_order_id,
                routing_key=build_routing_key(
                    work_order.org_id,
                    residence_id,
                    request.category,
                ),
                actor_user_id=contractor_user_id,
                connector=connector,
                data={"request_id": str(request.request_id)},
            )
        return work_order, integration_job

    def list_requested_integration_jobs(
        self,
        *,
        limit: int = 100,
    ) -> list[IntegrationJob]:
        return list(
            self.session.scalars(
                select(IntegrationJob)
                .where(IntegrationJob.status == IntegrationJobStatus.requested)
                .order_by(IntegrationJob.created_at.asc())
                .limit(limit)
            )
        )

    def record_integration_job_outcome(
        self,
        *,
        job_id: uuid.UUID,
        succeeded: bool,
        actor_user_id: uuid.UUID | None = None,
        error_message: str | None = None,
    ) -> IntegrationJob:
        integration_job = self.session.get(IntegrationJob, job_id)
        if integration_job is None:
            raise ValueError(f"IntegrationJob {job_id} does not exist")

        integration_job.attempts += 1
        integration_job.updated_at = datetime.now(timezone.utc)
        if succeeded:
            integration_job.status = IntegrationJobStatus.completed
            integration_job.last_error = None
            event_type = EVENT_INTEGRATION_COMPLETED
        else:
            integration_job.status = IntegrationJobStatus.failed
            integration_job.last_error = error_message
            event_type = EVENT_INTEGRATION_FAILED
        self.session.flush()

        work_order = self.session.get(WorkOrder, integration_job.work_order_id)
        if work_order is None:
            raise ValueError(f"WorkOrder {integration_job.work_order_id} does not exist")
        request = self.session.get(MaintenanceRequest, work_order.request_id)
        if request is None:
            raise ValueError(f"MaintenanceRequest {work_order.request_id} does not exist")

        residence_id = self._get_residence_id_for_unit(request.unit_id)
        self._append_event(
            event_type=event_type,
            subject_id=integration_job.job_id,
            partition_key=str(work_order.work_order_id),
            routing_key=build_routing_key(work_order.org_id, residence_id, request.category),
            actor_user_id=actor_user_id,
            data={
                "job_id": str(integration_job.job_id),
                "status": integration_job.status.value,
                "attempts": integration_job.attempts,
                "last_error": integration_job.last_error,
            },
        )
        return integration_job

    # Backward-compatible aliases for existing scripts.
    def create_work_order_from_request(
        self,
        *,
        request_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        contractor_user_id_override: uuid.UUID | None = None,
        connector: str = "notify_contractor",
    ) -> tuple[WorkOrder, IntegrationJob]:
        return self.dispatch_request_to_work_order(
            request_id=request_id,
            staff_user_id=actor_user_id,
            contractor_user_id_override=contractor_user_id_override,
            connector=connector,
        )

    def transition_work_order_status(
        self,
        *,
        work_order_id: uuid.UUID,
        to_status: WorkOrderStatus | str,
        actor_user_id: uuid.UUID,
    ) -> WorkOrder:
        normalized = to_status if isinstance(to_status, WorkOrderStatus) else WorkOrderStatus(to_status)
        if normalized == WorkOrderStatus.in_progress:
            return self.contractor_start_job(
                work_order_id=work_order_id,
                contractor_user_id=actor_user_id,
            )
        if normalized == WorkOrderStatus.completed:
            work_order, _ = self.contractor_complete_job(
                work_order_id=work_order_id,
                contractor_user_id=actor_user_id,
            )
            return work_order
        raise InvalidWorkOrderTransitionError(f"Unsupported target status {normalized.value}")

    def finalize_integration_job(
        self,
        *,
        job_id: uuid.UUID,
        succeeded: bool,
        actor_user_id: uuid.UUID | None = None,
        error_message: str | None = None,
    ) -> IntegrationJob:
        return self.record_integration_job_outcome(
            job_id=job_id,
            succeeded=succeeded,
            actor_user_id=actor_user_id,
            error_message=error_message,
        )
