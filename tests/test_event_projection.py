from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import uuid

from app.models import JobStatus, UserRole
from app.services import apply_status_change, derive_job_status_from_events, sync_job_status_from_events


@dataclass
class StubEvent:
    id: uuid.UUID
    created_at: datetime
    target_status: JobStatus | None
    event_type: str = "note"
    message: str = ""


@dataclass
class StubJob:
    status: JobStatus
    events: list[StubEvent]
    assigned_org_id: uuid.UUID | None = None
    assigned_contractor_user_id: uuid.UUID | None = None


@dataclass
class StubActor:
    role: UserRole
    organisation_id: uuid.UUID | None = None


def test_derive_job_status_from_events_falls_back_to_new_when_all_target_status_values_are_null() -> None:
    created_at = datetime(2026, 3, 21, 12, 0, tzinfo=timezone.utc)
    events = [
        StubEvent(id=uuid.uuid4(), created_at=created_at, target_status=None),
        StubEvent(id=uuid.uuid4(), created_at=created_at, target_status=None, event_type="assignment"),
    ]

    assert derive_job_status_from_events(events) == JobStatus.new


def test_derive_job_status_from_events_uses_last_non_null_target_status() -> None:
    events = [
        StubEvent(
            id=uuid.uuid4(),
            created_at=datetime(2026, 3, 21, 10, 0, tzinfo=timezone.utc),
            target_status=JobStatus.assigned,
        ),
        StubEvent(
            id=uuid.uuid4(),
            created_at=datetime(2026, 3, 21, 11, 0, tzinfo=timezone.utc),
            target_status=JobStatus.completed,
        ),
    ]

    assert derive_job_status_from_events(events) == JobStatus.completed


def test_derive_job_status_from_events_ignores_note_events_with_null_target_status() -> None:
    events = [
        StubEvent(
            id=uuid.uuid4(),
            created_at=datetime(2026, 3, 21, 10, 0, tzinfo=timezone.utc),
            target_status=JobStatus.scheduled,
            event_type="schedule",
        ),
        StubEvent(
            id=uuid.uuid4(),
            created_at=datetime(2026, 3, 21, 11, 0, tzinfo=timezone.utc),
            target_status=None,
            event_type="note",
            message="Called resident to confirm access",
        ),
    ]

    assert derive_job_status_from_events(events) == JobStatus.scheduled


def test_derive_job_status_from_events_uses_id_to_break_same_timestamp_ties() -> None:
    created_at = datetime(2026, 3, 21, 12, 0, tzinfo=timezone.utc)
    later_id = uuid.UUID("00000000-0000-0000-0000-0000000000b0")
    earlier_id = uuid.UUID("00000000-0000-0000-0000-0000000000a0")
    events = [
        StubEvent(id=later_id, created_at=created_at, target_status=JobStatus.completed),
        StubEvent(id=earlier_id, created_at=created_at, target_status=JobStatus.assigned),
    ]

    assert derive_job_status_from_events(events) == JobStatus.completed


def test_sync_job_status_from_events_updates_job_status_from_derived_projection() -> None:
    job = StubJob(
        status=JobStatus.new,
        events=[
            StubEvent(
                id=uuid.uuid4(),
                created_at=datetime(2026, 3, 21, 10, 0, tzinfo=timezone.utc),
                target_status=JobStatus.triaged,
            )
        ],
    )

    assert sync_job_status_from_events(job) == JobStatus.triaged
    assert job.status == JobStatus.triaged


def test_apply_status_change_returns_event_spec_without_mutating_job_status() -> None:
    actor = StubActor(role=UserRole.triage_officer)
    job = StubJob(status=JobStatus.assigned, events=[])

    event = apply_status_change(job, JobStatus.triaged, actor)

    assert event is not None
    assert event.target_status == JobStatus.triaged
    assert job.status == JobStatus.assigned
