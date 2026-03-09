from __future__ import annotations

import unittest
import uuid

from app.models import AuditEntry, DomainEvent, EVENT_INTEGRATION_REQUESTED, IntegrationJobStatus
from app.services.events import append_event, request_integration_job


class RecordingSession:
    def __init__(self, generated_ids: list[uuid.UUID] | None = None) -> None:
        self.added: list[object] = []
        self.flush_count = 0
        self._generated_ids = iter(generated_ids or [])

    def add(self, obj: object) -> None:
        self.added.append(obj)

    def flush(self) -> None:
        self.flush_count += 1
        for obj in self.added:
            self._assign_identity(obj)

    def _assign_identity(self, obj: object) -> None:
        for attribute in ("event_id", "job_id", "audit_id"):
            if hasattr(obj, attribute) and getattr(obj, attribute) is None:
                setattr(obj, attribute, next(self._generated_ids))
                return


class EventServiceTests(unittest.TestCase):
    def test_append_event_creates_domain_event_and_audit_entry(self) -> None:
        event_id = uuid.uuid4()
        audit_id = uuid.uuid4()
        actor_user_id = uuid.uuid4()
        subject_id = uuid.uuid4()
        session = RecordingSession(generated_ids=[event_id, audit_id])

        event = append_event(
            session,
            source="fixhub.tests",
            event_type="uon.work_order.created",
            subject_id=subject_id,
            partition_key="work-order-1",
            routing_key="org.test.residence.test.category.plumbing",
            actor_user_id=actor_user_id,
            data={"request_id": "request-1"},
        )

        self.assertIsInstance(event, DomainEvent)
        self.assertEqual(event.event_id, event_id)
        self.assertEqual(event.subject_id, subject_id)
        self.assertEqual(event.actor_user_id, actor_user_id)
        self.assertEqual(event.data, {"request_id": "request-1"})
        self.assertEqual(session.flush_count, 1)
        self.assertEqual(len(session.added), 2)
        self.assertIsInstance(session.added[1], AuditEntry)
        self.assertEqual(session.added[1].event_id, event_id)

    def test_request_integration_job_links_event_and_outbox_job(self) -> None:
        event_id = uuid.uuid4()
        audit_id = uuid.uuid4()
        actor_user_id = uuid.uuid4()
        job_id = uuid.uuid4()
        work_order_id = uuid.uuid4()
        session = RecordingSession(generated_ids=[event_id, audit_id])

        integration_job = request_integration_job(
            session,
            source="fixhub.tests",
            work_order_id=work_order_id,
            routing_key="org.test.residence.test.category.plumbing",
            actor_user_id=actor_user_id,
            connector="notify_contractor",
            data={"request_id": "request-1"},
            job_id=job_id,
        )

        event = session.added[0]
        audit_entry = session.added[1]

        self.assertIsInstance(event, DomainEvent)
        self.assertIsInstance(audit_entry, AuditEntry)
        self.assertEqual(event.event_id, event_id)
        self.assertEqual(event.type, EVENT_INTEGRATION_REQUESTED)
        self.assertEqual(event.subject_id, job_id)
        self.assertEqual(event.partition_key, str(work_order_id))
        self.assertEqual(
            event.data,
            {
                "job_id": str(job_id),
                "connector": "notify_contractor",
                "status": IntegrationJobStatus.requested.value,
                "request_id": "request-1",
            },
        )
        self.assertEqual(integration_job.job_id, job_id)
        self.assertEqual(integration_job.event_id, event_id)
        self.assertEqual(integration_job.work_order_id, work_order_id)
        self.assertEqual(integration_job.status, IntegrationJobStatus.requested)
        self.assertEqual(integration_job.attempts, 0)
        self.assertEqual(audit_entry.event_id, event_id)
        self.assertEqual(session.flush_count, 2)
