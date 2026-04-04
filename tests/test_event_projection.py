from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import uuid

from app.models import EventType, JobStatus, ResponsibilityOwner, ResponsibilityStage, UserRole
from app.api.deps import serialize_related_job
from app.services import (
    apply_status_change,
    derive_assignment_projection,
    derive_coordination_projection,
    derive_job_status_from_events,
    latest_role_update,
    sync_job_status_from_events,
)


@dataclass
class StubEvent:
    id: uuid.UUID
    created_at: datetime
    target_status: JobStatus | None
    event_type: EventType | str = "note"
    message: str = ""
    reason_code: str | None = None
    responsibility_stage: ResponsibilityStage | None = None
    owner_scope: str | None = None
    responsibility_owner: ResponsibilityOwner | None = None


@dataclass
class StubJob:
    status: JobStatus
    events: list[StubEvent]
    assigned_org_id: uuid.UUID | None = None
    assigned_contractor_user_id: uuid.UUID | None = None
    assigned_org: object | None = None
    assigned_contractor: object | None = None


@dataclass
class StubActor:
    role: UserRole
    organisation_id: uuid.UUID | None = None


@dataclass
class StubAssignee:
    name: str


@dataclass
class StubCreator:
    name: str


@dataclass
class StubAssignmentEvent(StubEvent):
    assigned_org_id: uuid.UUID | None = None
    assigned_org: object | None = None
    assigned_contractor_user_id: uuid.UUID | None = None
    assigned_contractor: object | None = None


@dataclass
class StubRelatedJob:
    id: uuid.UUID
    title: str
    status: JobStatus
    events: list[StubEvent]
    creator: StubCreator
    created_at: datetime
    updated_at: datetime
    asset_id: uuid.UUID | None = None


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


def test_coordination_projection_uses_status_timeline_and_assignment_context() -> None:
    job = StubJob(
        status=JobStatus.scheduled,
        assigned_org=StubAssignee(name="Newcastle Plumbing"),
        events=[
            StubEvent(
                id=uuid.uuid4(),
                created_at=datetime(2026, 3, 21, 10, 0, tzinfo=timezone.utc),
                target_status=JobStatus.assigned,
                event_type=EventType.status_change,
                message="Marked job assigned",
                responsibility_stage=ResponsibilityStage.triage,
                responsibility_owner=ResponsibilityOwner.coordinator,
            ),
            StubEvent(
                id=uuid.uuid4(),
                created_at=datetime(2026, 3, 21, 11, 0, tzinfo=timezone.utc),
                target_status=JobStatus.scheduled,
                event_type=EventType.schedule,
                message="Scheduled site visit",
                responsibility_stage=ResponsibilityStage.coordination,
                responsibility_owner=ResponsibilityOwner.triage_officer,
            ),
        ],
    )

    projection = derive_coordination_projection(job, job.events)

    assert projection.status == JobStatus.scheduled
    assert projection.headline == "Visit scheduled; waiting for contractor attendance"
    assert projection.owner_label == "Newcastle Plumbing"
    assert projection.responsibility_stage == "coordination"
    assert projection.responsibility_owner == "triage_officer"
    assert projection.latest_event_type == "schedule"


def test_assignment_projection_prefers_explicit_assignment_events_over_drifted_job_row() -> None:
    event_org_id = uuid.uuid4()
    drifted_org_id = uuid.uuid4()
    job = StubJob(
        status=JobStatus.assigned,
        assigned_org_id=drifted_org_id,
        assigned_org=StubAssignee(name="Drifted Row Org"),
        events=[
            StubAssignmentEvent(
                id=uuid.uuid4(),
                created_at=datetime(2026, 3, 21, 10, 0, tzinfo=timezone.utc),
                target_status=None,
                event_type=EventType.assignment,
                assigned_org_id=event_org_id,
                assigned_org=StubAssignee(name="Newcastle Plumbing"),
            )
        ],
    )

    assignment = derive_assignment_projection(job, job.events)

    assert assignment.assigned_org_id == event_org_id
    assert assignment.assigned_org_name == "Newcastle Plumbing"
    assert assignment.assignee_scope == "organisation"
    assert assignment.assignee_label == "Newcastle Plumbing"


def test_coordination_projection_keeps_block_reason_visible_after_note_event() -> None:
    job = StubJob(
        status=JobStatus.blocked,
        assigned_contractor=StubAssignee(name="Devon Contractor"),
        events=[
            StubEvent(
                id=uuid.uuid4(),
                created_at=datetime(2026, 3, 21, 11, 0, tzinfo=timezone.utc),
                target_status=JobStatus.blocked,
                event_type=EventType.status_change,
                message="Marked job blocked",
                reason_code="awaiting_access",
                responsibility_stage=ResponsibilityStage.execution,
            ),
            StubEvent(
                id=uuid.uuid4(),
                created_at=datetime(2026, 3, 21, 12, 0, tzinfo=timezone.utc),
                target_status=None,
                event_type=EventType.note,
                message="Resident contacted about access window",
            ),
        ],
    )

    projection = derive_coordination_projection(job, job.events)

    assert projection.status == JobStatus.blocked
    assert projection.detail == "awaiting_access"
    assert projection.owner_label == "Dispatch coordinator"
    assert projection.latest_event_type == "note"
    assert projection.responsibility_owner == "coordinator"


def test_coordination_projection_keeps_scheduled_detail_tied_to_schedule_event_after_note() -> None:
    job = StubJob(
        status=JobStatus.scheduled,
        assigned_org=StubAssignee(name="Newcastle Plumbing"),
        events=[
            StubEvent(
                id=uuid.uuid4(),
                created_at=datetime(2026, 3, 21, 11, 0, tzinfo=timezone.utc),
                target_status=JobStatus.scheduled,
                event_type=EventType.schedule,
                message="Resident approved Friday morning access window",
                responsibility_stage=ResponsibilityStage.coordination,
            ),
            StubEvent(
                id=uuid.uuid4(),
                created_at=datetime(2026, 3, 21, 12, 0, tzinfo=timezone.utc),
                target_status=None,
                event_type=EventType.note,
                message="Front desk left voicemail for the resident",
            ),
        ],
    )

    projection = derive_coordination_projection(job, job.events)

    assert projection.status == JobStatus.scheduled
    assert projection.detail == "Resident approved Friday morning access window"
    assert projection.owner_label == "Newcastle Plumbing"
    assert projection.latest_event_type == "note"


def test_coordination_projection_shows_completion_detail_but_returns_next_owner_to_resident() -> None:
    job = StubJob(
        status=JobStatus.completed,
        assigned_org=StubAssignee(name="Newcastle Plumbing"),
        events=[
            StubEvent(
                id=uuid.uuid4(),
                created_at=datetime(2026, 3, 21, 11, 0, tzinfo=timezone.utc),
                target_status=JobStatus.completed,
                event_type=EventType.completion,
                message="Tap washer replaced and sink tested with no further leak",
                responsibility_stage=ResponsibilityStage.execution,
            ),
            StubEvent(
                id=uuid.uuid4(),
                created_at=datetime(2026, 3, 21, 12, 0, tzinfo=timezone.utc),
                target_status=None,
                event_type=EventType.note,
                message="Invoice reference added to the file",
            ),
        ],
    )

    projection = derive_coordination_projection(job, job.events)

    assert projection.status == JobStatus.completed
    assert projection.detail == "Tap washer replaced and sink tested with no further leak"
    assert projection.owner_label == "Resident"
    assert projection.latest_event_type == "note"


def test_coordination_projection_prefers_latest_structured_note_over_stale_status_headline() -> None:
    job = StubJob(
        status=JobStatus.scheduled,
        assigned_org=StubAssignee(name="Newcastle Plumbing"),
        events=[
            StubEvent(
                id=uuid.uuid4(),
                created_at=datetime(2026, 3, 21, 11, 0, tzinfo=timezone.utc),
                target_status=JobStatus.scheduled,
                event_type=EventType.schedule,
                message="Resident approved Friday morning access window",
                responsibility_stage=ResponsibilityStage.coordination,
                responsibility_owner=ResponsibilityOwner.triage_officer,
            ),
            StubEvent(
                id=uuid.uuid4(),
                created_at=datetime(2026, 3, 21, 12, 0, tzinfo=timezone.utc),
                target_status=None,
                event_type=EventType.note,
                message="Resident requested a new access window after the original booking",
                reason_code="resident_access_issue",
                responsibility_stage=ResponsibilityStage.coordination,
                responsibility_owner=ResponsibilityOwner.coordinator,
            ),
        ],
    )

    projection = derive_coordination_projection(job, job.events)

    assert projection.status == JobStatus.scheduled
    assert projection.headline == "Coordination follow-up recorded without changing lifecycle state"
    assert projection.owner_label == "Dispatch coordinator"
    assert projection.detail == "Resident requested a new access window after the original booking"


def test_coordination_projection_labels_assignment_only_signal_explicitly() -> None:
    job = StubJob(
        status=JobStatus.triaged,
        assigned_org=StubAssignee(name="Campus Maintenance"),
        events=[
            StubEvent(
                id=uuid.uuid4(),
                created_at=datetime(2026, 3, 21, 11, 0, tzinfo=timezone.utc),
                target_status=JobStatus.triaged,
                event_type=EventType.status_change,
                message="Triage review recorded",
                responsibility_stage=ResponsibilityStage.triage,
                responsibility_owner=ResponsibilityOwner.triage_officer,
            ),
            StubAssignmentEvent(
                id=uuid.uuid4(),
                created_at=datetime(2026, 3, 21, 12, 0, tzinfo=timezone.utc),
                target_status=None,
                event_type=EventType.assignment,
                message="Reassigned Campus Maintenance",
                responsibility_stage=ResponsibilityStage.triage,
                responsibility_owner=ResponsibilityOwner.coordinator,
                assigned_org_id=uuid.uuid4(),
                assigned_org=StubAssignee(name="Campus Maintenance"),
            ),
        ],
    )

    projection = derive_coordination_projection(job, job.events)

    assert projection.status == JobStatus.triaged
    assert projection.headline == "Dispatch target updated without changing lifecycle state"
    assert projection.owner_label == "Dispatch coordinator"
    assert projection.detail == "Reassigned Campus Maintenance"


def test_latest_role_update_skips_generic_status_echoes_and_prefers_real_handoff_message() -> None:
    org = type("Org", (), {"name": "Student Living"})()
    actor = type("Actor", (), {"role": UserRole.triage_officer, "name": "Priya Property Manager", "organisation": org})()
    events = [
        StubAssignmentEvent(
            id=uuid.uuid4(),
            created_at=datetime(2026, 3, 21, 11, 0, tzinfo=timezone.utc),
            target_status=None,
            event_type=EventType.assignment,
            message="Assigned Newcastle Plumbing",
        ),
        StubEvent(
            id=uuid.uuid4(),
            created_at=datetime(2026, 3, 21, 12, 0, tzinfo=timezone.utc),
            target_status=JobStatus.triaged,
            event_type=EventType.status_change,
            message="Triage review recorded",
        ),
    ]
    for event in events:
        event.actor_user = actor

    update = latest_role_update(events, roles={UserRole.triage_officer.value})

    assert update is not None
    assert update.message == "Assigned Newcastle Plumbing"
    assert update.actor_label == "Priya Property Manager (Student Living)"


def test_coordination_projection_does_not_stitch_owner_metadata_from_different_events() -> None:
    job = StubJob(
        status=JobStatus.scheduled,
        assigned_org=StubAssignee(name="Newcastle Plumbing"),
        events=[
            StubEvent(
                id=uuid.uuid4(),
                created_at=datetime(2026, 3, 21, 11, 0, tzinfo=timezone.utc),
                target_status=JobStatus.scheduled,
                event_type=EventType.schedule,
                message="Booked plumber for Friday morning attendance",
                responsibility_stage=ResponsibilityStage.coordination,
                responsibility_owner=ResponsibilityOwner.contractor,
                owner_scope="organisation",
            ),
            StubEvent(
                id=uuid.uuid4(),
                created_at=datetime(2026, 3, 21, 12, 0, tzinfo=timezone.utc),
                target_status=None,
                event_type=EventType.note,
                message="Resident asked for an afternoon swap",
                reason_code="resident_access_issue",
                responsibility_stage=ResponsibilityStage.coordination,
            ),
        ],
    )

    projection = derive_coordination_projection(job, job.events)

    assert projection.headline == "Coordination follow-up recorded without changing lifecycle state"
    assert projection.detail == "Resident asked for an afternoon swap"
    assert projection.responsibility_stage == "coordination"
    assert projection.responsibility_owner is None
    assert projection.owner_scope is None


def test_serialize_related_job_uses_event_derived_status_instead_of_row_cache() -> None:
    created_at = datetime(2026, 3, 21, 11, 0, tzinfo=timezone.utc)
    earlier_job = StubRelatedJob(
        id=uuid.uuid4(),
        title="Earlier sink leak",
        status=JobStatus.triaged,
        events=[
            StubEvent(
                id=uuid.uuid4(),
                created_at=created_at,
                target_status=JobStatus.completed,
                event_type=EventType.completion,
                message="Repair completed on site",
                responsibility_stage=ResponsibilityStage.execution,
            )
        ],
        creator=StubCreator(name="Riley Resident"),
        created_at=created_at,
        updated_at=created_at,
    )
    current_job = StubRelatedJob(
        id=uuid.uuid4(),
        title="Current sink leak",
        status=JobStatus.new,
        events=[],
        creator=StubCreator(name="Riley Resident"),
        created_at=created_at,
        updated_at=created_at,
    )

    related = serialize_related_job(earlier_job, current_job=current_job)

    assert related["status"] == "completed"
    assert related["status_label"] == "Completed"
    assert related["coordination_headline"] == "Work marked complete"
