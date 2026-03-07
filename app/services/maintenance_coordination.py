from __future__ import annotations

import uuid
from datetime import datetime, timezone

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
    WorkOrder,
    WorkOrderStatus,
)
from app.services.routing import lookup_contractor_user_id


class InvalidWorkOrderTransitionError(ValueError):
    pass


_ALLOWED_TRANSITIONS: dict[WorkOrderStatus, set[WorkOrderStatus]] = {
    WorkOrderStatus.assigned: {WorkOrderStatus.in_progress},
    WorkOrderStatus.in_progress: {WorkOrderStatus.completed},
    WorkOrderStatus.completed: set(),
}


def build_routing_key(org_id: uuid.UUID, residence_id: uuid.UUID, category: str) -> str:
    return f"org.{org_id}.residence.{residence_id}.category.{category}"


class MaintenanceCoordinationService:
    def __init__(self, session: Session, source: str = settings.event_source) -> None:
        self.session = session
        self.source = source

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
        subject_type: str,
        subject_id: uuid.UUID,
        partition_key: str,
        routing_key: str,
        actor_user_id: uuid.UUID | None,
        data: dict[str, object] | None = None,
    ) -> DomainEvent:
        event = DomainEvent(
            type=event_type,
            source=self.source,
            subject_type=subject_type,
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

        routing_key = build_routing_key(org_id, residence_id, category)
        self._append_event(
            event_type=EVENT_MAINTENANCE_REQUEST_SUBMITTED,
            subject_type="maintenance_request",
            subject_id=request.request_id,
            partition_key=str(org_id),
            routing_key=routing_key,
            actor_user_id=resident_user_id,
            data={
                "request_id": str(request.request_id),
                "category": category,
            },
        )
        return request

    def create_work_order_from_request(
        self,
        *,
        request_id: uuid.UUID,
        actor_user_id: uuid.UUID | None = None,
        connector: str = "notify_contractor",
    ) -> tuple[WorkOrder, IntegrationJob]:
        request = self.session.get(MaintenanceRequest, request_id)
        if request is None:
            raise ValueError(f"MaintenanceRequest {request_id} does not exist")

        existing_work_order_id = self.session.scalar(
            select(WorkOrder.work_order_id).where(WorkOrder.request_id == request_id).limit(1)
        )
        if existing_work_order_id is not None:
            raise ValueError(
                f"WorkOrder already exists for request_id={request_id}: {existing_work_order_id}"
            )

        residence_id = self._get_residence_id_for_unit(request.unit_id)
        contractor_user_id = lookup_contractor_user_id(
            self.session,
            residence_id=residence_id,
            category=request.category,
        )

        work_order = WorkOrder(
            org_id=request.org_id,
            request_id=request.request_id,
            contractor_user_id=contractor_user_id,
            status=WorkOrderStatus.assigned,
        )
        self.session.add(work_order)
        self.session.flush()

        routing_key = build_routing_key(request.org_id, residence_id, request.category)
        work_order_created_event = self._append_event(
            event_type=EVENT_WORK_ORDER_CREATED,
            subject_type="work_order",
            subject_id=work_order.work_order_id,
            partition_key=str(work_order.work_order_id),
            routing_key=routing_key,
            actor_user_id=actor_user_id,
            data={
                "request_id": str(request.request_id),
                "contractor_user_id": str(contractor_user_id),
                "status": work_order.status.value,
            },
        )

        integration_job = IntegrationJob(
            event_id=work_order_created_event.event_id,
            work_order_id=work_order.work_order_id,
            connector=connector,
            status=IntegrationJobStatus.requested,
            attempts=0,
        )
        self.session.add(integration_job)
        self.session.flush()

        self._append_event(
            event_type=EVENT_INTEGRATION_REQUESTED,
            subject_type="integration_job",
            subject_id=integration_job.job_id,
            partition_key=str(work_order.work_order_id),
            routing_key=routing_key,
            actor_user_id=actor_user_id,
            data={
                "job_id": str(integration_job.job_id),
                "connector": integration_job.connector,
                "status": integration_job.status.value,
            },
        )
        return work_order, integration_job

    def transition_work_order_status(
        self,
        *,
        work_order_id: uuid.UUID,
        to_status: WorkOrderStatus | str,
        actor_user_id: uuid.UUID | None = None,
    ) -> WorkOrder:
        if isinstance(to_status, str):
            to_status = WorkOrderStatus(to_status)

        work_order = self.session.get(WorkOrder, work_order_id)
        if work_order is None:
            raise ValueError(f"WorkOrder {work_order_id} does not exist")

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
        routing_key = build_routing_key(work_order.org_id, residence_id, request.category)
        self._append_event(
            event_type=EVENT_WORK_ORDER_STATUS_CHANGED,
            subject_type="work_order",
            subject_id=work_order.work_order_id,
            partition_key=str(work_order.work_order_id),
            routing_key=routing_key,
            actor_user_id=actor_user_id,
            data={
                "from_status": previous_status.value,
                "to_status": to_status.value,
            },
        )
        return work_order

    def finalize_integration_job(
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
        routing_key = build_routing_key(work_order.org_id, residence_id, request.category)

        self._append_event(
            event_type=event_type,
            subject_type="integration_job",
            subject_id=integration_job.job_id,
            partition_key=str(work_order.work_order_id),
            routing_key=routing_key,
            actor_user_id=actor_user_id,
            data={
                "job_id": str(integration_job.job_id),
                "status": integration_job.status.value,
                "attempts": integration_job.attempts,
                "last_error": integration_job.last_error,
            },
        )
        return integration_job