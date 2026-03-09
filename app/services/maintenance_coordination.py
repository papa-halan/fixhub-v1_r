from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    EVENT_INTEGRATION_COMPLETED,
    EVENT_INTEGRATION_FAILED,
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
from app.services.events import append_event, request_integration_job
from app.services.policy import AuthorisationPolicy
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


@dataclass(frozen=True)
class ResidentRequestStatus:
    request: MaintenanceRequest
    work_order: WorkOrder | None


@dataclass(frozen=True)
class DispatchRequestToWorkOrderCommand:
    request_id: uuid.UUID
    staff_user_id: uuid.UUID
    contractor_user_id_override: uuid.UUID | None = None
    connector: str = "notify_contractor"


@dataclass(frozen=True)
class DispatchContractorResolution:
    contractor_user_id: uuid.UUID
    dispatch_mode: str
    residence_id: uuid.UUID


class MaintenanceCoordinationService:
    def __init__(
        self,
        session: Session,
        source: str = settings.event_source,
        policy: AuthorisationPolicy | None = None,
    ) -> None:
        self.session = session
        self.source = source
        self.policy = policy or AuthorisationPolicy(session)

    def _get_maintenance_request(self, request_id: uuid.UUID) -> MaintenanceRequest:
        request = self.session.get(MaintenanceRequest, request_id)
        if request is None:
            raise ValueError(f"MaintenanceRequest {request_id} does not exist")
        return request

    def _get_work_order(self, work_order_id: uuid.UUID) -> WorkOrder:
        work_order = self.session.get(WorkOrder, work_order_id)
        if work_order is None:
            raise ValueError(f"WorkOrder {work_order_id} does not exist")
        return work_order

    def _get_integration_job(self, job_id: uuid.UUID) -> IntegrationJob:
        integration_job = self.session.get(IntegrationJob, job_id)
        if integration_job is None:
            raise ValueError(f"IntegrationJob {job_id} does not exist")
        return integration_job

    def _get_residence_id_for_unit(self, unit_id: uuid.UUID) -> uuid.UUID:
        residence_id = self.session.scalar(
            select(Unit.residence_id).where(Unit.unit_id == unit_id).limit(1)
        )
        if residence_id is None:
            raise ValueError(f"Unit {unit_id} does not exist")
        return residence_id

    def _ensure_request_has_no_work_order(self, request_id: uuid.UUID) -> None:
        existing_work_order_id = self.session.scalar(
            select(WorkOrder.work_order_id).where(WorkOrder.request_id == request_id).limit(1)
        )
        if existing_work_order_id is not None:
            raise ValueError(
                f"WorkOrder already exists for request_id={request_id}: {existing_work_order_id}"
            )

    def _load_dispatch_request(
        self,
        command: DispatchRequestToWorkOrderCommand,
    ) -> MaintenanceRequest:
        request = self._get_maintenance_request(command.request_id)
        self.policy.require_staff(user_id=command.staff_user_id, org_id=request.org_id)
        self._ensure_request_has_no_work_order(command.request_id)
        return request

    def _resolve_dispatch_contractor(
        self,
        *,
        command: DispatchRequestToWorkOrderCommand,
        request: MaintenanceRequest,
    ) -> DispatchContractorResolution:
        residence_id = self._get_residence_id_for_unit(request.unit_id)
        if command.contractor_user_id_override is not None:
            contractor = self.policy.require_contractor(
                user_id=command.contractor_user_id_override,
                org_id=request.org_id,
            )
            return DispatchContractorResolution(
                contractor_user_id=contractor.user_id,
                dispatch_mode="override",
                residence_id=residence_id,
            )

        contractor_user_id = lookup_contractor_user_id(
            self.session,
            residence_id=residence_id,
            category=request.category,
        )
        contractor = self.policy.require_contractor(
            user_id=contractor_user_id,
            org_id=request.org_id,
        )
        return DispatchContractorResolution(
            contractor_user_id=contractor.user_id,
            dispatch_mode="routing_rule",
            residence_id=residence_id,
        )

    def _create_work_order_for_dispatch(
        self,
        *,
        request: MaintenanceRequest,
        resolution: DispatchContractorResolution,
    ) -> WorkOrder:
        work_order = WorkOrder(
            org_id=request.org_id,
            request_id=request.request_id,
            contractor_user_id=resolution.contractor_user_id,
            status=WorkOrderStatus.assigned,
        )
        self.session.add(work_order)
        self.session.flush()
        return work_order

    def _emit_dispatched_work_order_event(
        self,
        *,
        command: DispatchRequestToWorkOrderCommand,
        request: MaintenanceRequest,
        work_order: WorkOrder,
        resolution: DispatchContractorResolution,
    ) -> str:
        routing_key = build_routing_key(
            request.org_id,
            resolution.residence_id,
            request.category,
        )
        append_event(
            self.session,
            source=self.source,
            event_type=EVENT_WORK_ORDER_CREATED,
            subject_id=work_order.work_order_id,
            partition_key=str(work_order.work_order_id),
            routing_key=routing_key,
            actor_user_id=command.staff_user_id,
            data={
                "request_id": str(request.request_id),
                "contractor_user_id": str(resolution.contractor_user_id),
                "status": work_order.status.value,
                "dispatch_mode": resolution.dispatch_mode,
            },
        )
        return routing_key

    def _request_dispatch_integration_job(
        self,
        *,
        command: DispatchRequestToWorkOrderCommand,
        request: MaintenanceRequest,
        work_order: WorkOrder,
        routing_key: str,
    ) -> IntegrationJob:
        return request_integration_job(
            self.session,
            source=self.source,
            work_order_id=work_order.work_order_id,
            routing_key=routing_key,
            actor_user_id=command.staff_user_id,
            connector=command.connector,
            data={"request_id": str(request.request_id)},
        )

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
        self.policy.require_resident(
            user_id=resident_user_id,
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

        append_event(
            self.session,
            source=self.source,
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
        request = self._get_maintenance_request(request_id)
        self.policy.require_request_owner(
            request=request,
            resident_user_id=resident_user_id,
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
        resolved_org_id = self.policy.resolve_staff_org_scope(
            staff_user_id=staff_user_id,
            requested_org_id=org_id,
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
        command = DispatchRequestToWorkOrderCommand(
            request_id=request_id,
            staff_user_id=staff_user_id,
            contractor_user_id_override=contractor_user_id_override,
            connector=connector,
        )
        request = self._load_dispatch_request(command)
        resolution = self._resolve_dispatch_contractor(command=command, request=request)
        work_order = self._create_work_order_for_dispatch(
            request=request,
            resolution=resolution,
        )
        routing_key = self._emit_dispatched_work_order_event(
            command=command,
            request=request,
            work_order=work_order,
            resolution=resolution,
        )
        integration_job = self._request_dispatch_integration_job(
            command=command,
            request=request,
            work_order=work_order,
            routing_key=routing_key,
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
        self.policy.require_contractor(user_id=contractor_user_id)
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
        work_order = self._get_work_order(work_order_id)
        self.policy.require_assigned_contractor(
            work_order=work_order,
            contractor_user_id=contractor_user_id,
        )

        allowed_next = _ALLOWED_TRANSITIONS[work_order.status]
        if to_status not in allowed_next:
            raise InvalidWorkOrderTransitionError(
                f"Invalid transition {work_order.status.value} -> {to_status.value}"
            )

        previous_status = work_order.status
        work_order.status = to_status
        self.session.flush()
        if to_status == WorkOrderStatus.completed:
            self.session.refresh(work_order, attribute_names=["completed_at"])

        request = self._get_maintenance_request(work_order.request_id)
        residence_id = self._get_residence_id_for_unit(request.unit_id)
        event_data: dict[str, object] = {
            "from": previous_status.value,
            "to": to_status.value,
        }
        if completion_note is not None:
            event_data["completion_note"] = completion_note

        append_event(
            self.session,
            source=self.source,
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
            request = self._get_maintenance_request(work_order.request_id)
            residence_id = self._get_residence_id_for_unit(request.unit_id)
            integration_job = request_integration_job(
                self.session,
                source=self.source,
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
        integration_job = self._get_integration_job(job_id)

        integration_job.attempts += 1
        if succeeded:
            integration_job.status = IntegrationJobStatus.completed
            integration_job.last_error = None
            event_type = EVENT_INTEGRATION_COMPLETED
        else:
            integration_job.status = IntegrationJobStatus.failed
            integration_job.last_error = error_message
            event_type = EVENT_INTEGRATION_FAILED
        self.session.flush()

        work_order = self._get_work_order(integration_job.work_order_id)
        request = self._get_maintenance_request(work_order.request_id)
        residence_id = self._get_residence_id_for_unit(request.unit_id)
        append_event(
            self.session,
            source=self.source,
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
