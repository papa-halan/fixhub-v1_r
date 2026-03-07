from __future__ import annotations

from collections import Counter

from sqlalchemy import func, or_, select

from app.core.database import session_scope
from app.models import (
    AuditEntry,
    DomainEvent,
    EVENT_INTEGRATION_COMPLETED,
    EVENT_INTEGRATION_REQUESTED,
    EVENT_MAINTENANCE_REQUEST_SUBMITTED,
    EVENT_WORK_ORDER_CREATED,
    EVENT_WORK_ORDER_STATUS_CHANGED,
    IntegrationJob,
    WorkOrderStatus,
)
from app.services.maintenance_coordination import (
    MaintenanceCoordinationService,
    build_routing_key,
)
from app.services.seed import ensure_seed_data


if __name__ == "__main__":
    with session_scope() as session:
        seed = ensure_seed_data(session)
        workflow = MaintenanceCoordinationService(session)

        maintenance_request = workflow.submit_maintenance_request(
            org_id=seed.org_id,
            unit_id=seed.unit_id,
            resident_user_id=seed.resident_user_id,
            category=seed.category,
            priority="normal",
            description="Kitchen tap is leaking.",
        )

        work_order, integration_job = workflow.create_work_order_from_request(
            request_id=maintenance_request.request_id,
            actor_user_id=seed.resident_user_id,
            connector="notify contractor",
        )

        workflow.transition_work_order_status(
            work_order_id=work_order.work_order_id,
            to_status=WorkOrderStatus.in_progress,
            actor_user_id=seed.contractor_user_id,
        )
        workflow.transition_work_order_status(
            work_order_id=work_order.work_order_id,
            to_status=WorkOrderStatus.completed,
            actor_user_id=seed.contractor_user_id,
        )

        workflow.finalize_integration_job(
            job_id=integration_job.job_id,
            succeeded=True,
            actor_user_id=seed.contractor_user_id,
        )

        session.flush()

        events = list(
            session.scalars(
                select(DomainEvent)
                .where(
                    or_(
                        DomainEvent.subject_id == maintenance_request.request_id,
                        DomainEvent.subject_id == work_order.work_order_id,
                        DomainEvent.subject_id == integration_job.job_id,
                    )
                )
                .order_by(DomainEvent.time.asc())
            )
        )

        assert len(events) == 6, f"Expected 6 events, got {len(events)}"

        type_counts = Counter(event.type for event in events)
        assert type_counts[EVENT_MAINTENANCE_REQUEST_SUBMITTED] == 1
        assert type_counts[EVENT_WORK_ORDER_CREATED] == 1
        assert type_counts[EVENT_WORK_ORDER_STATUS_CHANGED] == 2
        assert type_counts[EVENT_INTEGRATION_REQUESTED] == 1
        assert type_counts[EVENT_INTEGRATION_COMPLETED] == 1

        expected_routing_key = build_routing_key(seed.org_id, seed.residence_id, seed.category)
        for event in events:
            assert event.routing_key == expected_routing_key
            if event.type == EVENT_MAINTENANCE_REQUEST_SUBMITTED:
                assert event.partition_key == str(seed.org_id)
            else:
                assert event.partition_key == str(work_order.work_order_id)

        status_events = [
            event for event in events if event.type == EVENT_WORK_ORDER_STATUS_CHANGED
        ]
        to_status_values = {str(event.data.get("to_status")) for event in status_events}
        assert to_status_values == {"in_progress", "completed"}

        jobs = list(
            session.scalars(
                select(IntegrationJob).where(
                    IntegrationJob.work_order_id == work_order.work_order_id
                )
            )
        )
        assert len(jobs) == 1
        created_event = next(
            event for event in events if event.type == EVENT_WORK_ORDER_CREATED
        )
        assert jobs[0].event_id == created_event.event_id

        audit_count = session.scalar(
            select(func.count(AuditEntry.audit_id)).where(
                AuditEntry.event_id.in_([event.event_id for event in events])
            )
        )
        assert audit_count == len(events)

        assert work_order.status == WorkOrderStatus.completed
        assert work_order.completed_at is not None

    print("Smoke test passed:")
    print("  maintenance_request created")
    print("  work_order created via routing_rules")
    print("  status transitioned to in_progress then completed")
    print("  domain_events partition_key/routing_key assertions passed")
    print("  integration_job created on work_order.created")
    print("  audit_entries created for all events")