from __future__ import annotations

from collections import Counter

from sqlalchemy import func, select

from app.core.database import session_scope
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
    WorkOrderStatus,
)
from app.services.auth_service import login
from app.services.maintenance_coordination import (
    MaintenanceCoordinationService,
    build_routing_key,
)
from app.services.seed import ensure_seed_data


if __name__ == "__main__":
    with session_scope() as session:
        seed = ensure_seed_data(session)
        workflow = MaintenanceCoordinationService(session)

        resident = login(
            session=session,
            email="resident@uon.example",
            password="resident-password",
        )
        staff = login(
            session=session,
            email="staff@uon.example",
            password="staff-password",
        )
        contractor = login(
            session=session,
            email="contractor@uon.example",
            password="contractor-password",
        )

        request_default = workflow.submit_maintenance_request(
            org_id=seed.org_id,
            unit_id=seed.unit_id,
            resident_user_id=resident.user_id,
            category=seed.category,
            priority="normal",
            description="Kitchen tap is leaking.",
        )
        request_override = workflow.submit_maintenance_request(
            org_id=seed.org_id,
            unit_id=seed.unit_id,
            resident_user_id=resident.user_id,
            category=seed.category,
            priority="normal",
            description="Bathroom tap is leaking.",
        )

        unactioned = workflow.list_submitted_requests_without_work_order(
            staff_user_id=staff.user_id,
            org_id=seed.org_id,
        )
        unactioned_ids = {request.request_id for request in unactioned}
        assert request_default.request_id in unactioned_ids
        assert request_override.request_id in unactioned_ids

        work_order_default, integration_job_default = workflow.dispatch_request_to_work_order(
            request_id=request_default.request_id,
            staff_user_id=staff.user_id,
            connector="notify_contractor",
        )
        assert work_order_default.contractor_user_id == seed.contractor_user_id

        work_order_override, integration_job_override = workflow.dispatch_request_to_work_order(
            request_id=request_override.request_id,
            staff_user_id=staff.user_id,
            contractor_user_id_override=seed.override_contractor_user_id,
            connector="notify_contractor",
        )
        assert work_order_override.contractor_user_id == seed.override_contractor_user_id

        contractor_orders = workflow.list_assigned_work_orders(
            contractor_user_id=contractor.user_id,
            statuses=[WorkOrderStatus.assigned],
        )
        assert any(
            order.work_order_id == work_order_default.work_order_id for order in contractor_orders
        )

        workflow.contractor_start_job(
            work_order_id=work_order_default.work_order_id,
            contractor_user_id=contractor.user_id,
        )
        completed_work_order, resident_notification_job = workflow.contractor_complete_job(
            work_order_id=work_order_default.work_order_id,
            contractor_user_id=contractor.user_id,
            completion_note="Tap washer replaced and leak resolved.",
            create_resident_notification_job=True,
            connector="notify_resident",
        )
        assert completed_work_order.status == WorkOrderStatus.completed
        assert completed_work_order.completed_at is not None
        assert resident_notification_job is not None

        workflow.record_integration_job_outcome(
            job_id=integration_job_default.job_id,
            succeeded=True,
        )
        workflow.record_integration_job_outcome(
            job_id=resident_notification_job.job_id,
            succeeded=False,
            error_message="SMTP timeout",
        )

        resident_status = workflow.get_resident_request_status(
            resident_user_id=resident.user_id,
            request_id=request_default.request_id,
        )
        assert resident_status.work_order is not None
        assert resident_status.work_order.status == WorkOrderStatus.completed

        subject_ids = [
            request_default.request_id,
            request_override.request_id,
            work_order_default.work_order_id,
            work_order_override.work_order_id,
            integration_job_default.job_id,
            integration_job_override.job_id,
            resident_notification_job.job_id,
        ]
        events = list(
            session.scalars(
                select(DomainEvent)
                .where(DomainEvent.subject_id.in_(subject_ids))
                .order_by(DomainEvent.time.asc())
            )
        )

        assert len(events) == 11, f"Expected 11 events, got {len(events)}"

        type_counts = Counter(event.type for event in events)
        assert type_counts[EVENT_MAINTENANCE_REQUEST_SUBMITTED] == 2
        assert type_counts[EVENT_WORK_ORDER_CREATED] == 2
        assert type_counts[EVENT_WORK_ORDER_STATUS_CHANGED] == 2
        assert type_counts[EVENT_INTEGRATION_REQUESTED] == 3
        assert type_counts[EVENT_INTEGRATION_COMPLETED] == 1
        assert type_counts[EVENT_INTEGRATION_FAILED] == 1

        expected_routing_key = build_routing_key(seed.org_id, seed.residence_id, seed.category)
        for event in events:
            assert event.routing_key == expected_routing_key
            if event.type == EVENT_MAINTENANCE_REQUEST_SUBMITTED:
                assert event.partition_key == str(seed.org_id)
                assert event.actor_user_id == resident.user_id
            elif event.type == EVENT_WORK_ORDER_CREATED:
                assert event.partition_key == str(event.subject_id)
                assert event.actor_user_id == staff.user_id
            elif event.type == EVENT_WORK_ORDER_STATUS_CHANGED:
                assert event.partition_key == str(event.subject_id)
                assert event.subject_id == work_order_default.work_order_id
                assert event.actor_user_id == contractor.user_id
            elif event.subject_id in (
                integration_job_default.job_id,
                integration_job_override.job_id,
            ):
                assert event.partition_key in (
                    str(work_order_default.work_order_id),
                    str(work_order_override.work_order_id),
                )
                if event.type == EVENT_INTEGRATION_REQUESTED:
                    assert event.actor_user_id == staff.user_id
            elif event.subject_id == resident_notification_job.job_id:
                assert event.partition_key == str(work_order_default.work_order_id)
                if event.type == EVENT_INTEGRATION_REQUESTED:
                    assert event.actor_user_id == contractor.user_id
            else:
                assert event.partition_key == str(work_order_default.work_order_id)

        status_events = [
            event for event in events if event.type == EVENT_WORK_ORDER_STATUS_CHANGED
        ]
        assert {event.data.get("to") for event in status_events} == {
            WorkOrderStatus.in_progress.value,
            WorkOrderStatus.completed.value,
        }
        completed_event = next(
            event
            for event in status_events
            if event.data.get("to") == WorkOrderStatus.completed.value
        )
        assert completed_event.data.get("completion_note") == "Tap washer replaced and leak resolved."
        assert completed_event.actor_user_id == contractor.user_id

        requested_events_by_subject = {
            event.subject_id: event
            for event in events
            if event.type == EVENT_INTEGRATION_REQUESTED
        }
        jobs = {
            job.job_id: job
            for job in session.scalars(
                select(IntegrationJob).where(IntegrationJob.job_id.in_(list(requested_events_by_subject)))
            )
        }
        assert jobs[integration_job_default.job_id].event_id == requested_events_by_subject[
            integration_job_default.job_id
        ].event_id
        assert jobs[integration_job_override.job_id].event_id == requested_events_by_subject[
            integration_job_override.job_id
        ].event_id
        assert jobs[resident_notification_job.job_id].event_id == requested_events_by_subject[
            resident_notification_job.job_id
        ].event_id

        audit_count = session.scalar(
            select(func.count(AuditEntry.audit_id)).where(
                AuditEntry.event_id.in_([event.event_id for event in events])
            )
        )
        assert audit_count == len(events)

    print("Smoke test passed:")
    print("  resident submitted requests")
    print("  staff dispatched work orders (default routing + override)")
    print("  contractor started and completed a work order with completion note")
    print("  integration requested/completed/failed events emitted")
    print("  partition_key/routing_key/actor assertions passed")
    print("  every event has exactly one audit entry")
