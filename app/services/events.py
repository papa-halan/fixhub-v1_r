from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models import (
    AuditEntry,
    DomainEvent,
    EVENT_INTEGRATION_REQUESTED,
    IntegrationJob,
    IntegrationJobStatus,
)


def append_event(
    session: Session,
    *,
    source: str,
    event_type: str,
    subject_id: uuid.UUID,
    partition_key: str,
    routing_key: str,
    actor_user_id: uuid.UUID | None,
    data: dict[str, object] | None = None,
) -> DomainEvent:
    event = DomainEvent(
        type=event_type,
        source=source,
        subject_id=subject_id,
        partition_key=partition_key,
        routing_key=routing_key,
        actor_user_id=actor_user_id,
        data=data or {},
    )
    session.add(event)
    session.flush()
    session.add(AuditEntry(event_id=event.event_id))
    return event


def request_integration_job(
    session: Session,
    *,
    source: str,
    work_order_id: uuid.UUID,
    routing_key: str,
    actor_user_id: uuid.UUID | None,
    connector: str,
    data: dict[str, object] | None = None,
    partition_key: str | None = None,
    job_id: uuid.UUID | None = None,
) -> IntegrationJob:
    resolved_job_id = job_id or uuid.uuid4()
    event = append_event(
        session,
        source=source,
        event_type=EVENT_INTEGRATION_REQUESTED,
        subject_id=resolved_job_id,
        partition_key=partition_key or str(work_order_id),
        routing_key=routing_key,
        actor_user_id=actor_user_id,
        data={
            "job_id": str(resolved_job_id),
            "connector": connector,
            "status": IntegrationJobStatus.requested.value,
            **(data or {}),
        },
    )
    integration_job = IntegrationJob(
        job_id=resolved_job_id,
        event_id=event.event_id,
        work_order_id=work_order_id,
        connector=connector,
        status=IntegrationJobStatus.requested,
        attempts=0,
    )
    session.add(integration_job)
    session.flush()
    return integration_job
