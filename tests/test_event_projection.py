from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import uuid

from app.models import EventType, JobStatus, OwnerScope, ResponsibilityOwner, ResponsibilityStage, UserRole
from app.api.deps import (
    build_focus_counts,
    derive_queue_priority,
    derive_viewer_guidance,
    serialize_related_job,
    sort_jobs_for_queue,
)
from app.services import (
    apply_status_change,
    derive_assignment_projection,
    derive_coordination_projection,
    derive_job_status_from_events,
    derive_pending_signal,
    derive_visit_plan,
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
    assigned_org_name_snapshot: str | None = None
    assigned_contractor_user_id: uuid.UUID | None = None
    assigned_contractor: object | None = None
    assigned_contractor_name_snapshot: str | None = None


@dataclass
class StubRelatedJob:
    id: uuid.UUID
    title: str
    status: JobStatus
    events: list[StubEvent]
    creator: StubCreator
    created_at: datetime
    updated_at: datetime
    reported_for_user_name_snapshot: str | None = None
    location_id: uuid.UUID | None = None
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

    event = apply_status_change(
        job,
        JobStatus.triaged,
        actor,
        message="Reviewed the issue and confirmed it is ready for the next coordination step",
    )

    assert event is not None
    assert event.target_status == JobStatus.triaged
    assert job.status == JobStatus.assigned


def test_coordination_projection_uses_status_timeline_and_assignment_context() -> None:
    job = StubJob(
        status=JobStatus.scheduled,
        assigned_org_id=uuid.uuid4(),
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
    assert projection.owner_label == "Property manager"
    assert projection.action_required_by == "Newcastle Plumbing"
    assert projection.responsibility_stage == "coordination"
    assert projection.responsibility_owner == "triage_officer"
    assert projection.latest_event_type == "schedule"
    assert projection.latest_lifecycle_event_type == "schedule"


def test_apply_status_change_marks_scheduled_and_follow_up_as_operations_owned_coordination_states() -> None:
    actor = StubActor(role=UserRole.triage_officer)
    scheduled_job = StubJob(status=JobStatus.triaged, events=[])
    follow_up_job = StubJob(status=JobStatus.completed, events=[], assigned_org_id=uuid.uuid4())

    scheduled_event = apply_status_change(
        scheduled_job,
        JobStatus.scheduled,
        actor,
        message="Booked plumber for Friday morning attendance",
    )
    follow_up_event = apply_status_change(
        follow_up_job,
        JobStatus.follow_up_scheduled,
        actor,
        message="Booked a return visit after recurrence",
        reason_code="resident_reported_recurrence",
    )

    assert scheduled_event is not None
    assert scheduled_event.responsibility_stage == ResponsibilityStage.coordination
    assert scheduled_event.responsibility_owner == ResponsibilityOwner.triage_officer

    assert follow_up_event is not None
    assert follow_up_event.responsibility_stage == ResponsibilityStage.coordination
    assert follow_up_event.responsibility_owner == ResponsibilityOwner.triage_officer


def test_apply_status_change_marks_completion_as_resident_scope_after_execution_finishes() -> None:
    actor = StubActor(role=UserRole.contractor, organisation_id=uuid.uuid4())
    job = StubJob(
        status=JobStatus.in_progress,
        events=[],
        assigned_org_id=uuid.uuid4(),
    )

    completion_event = apply_status_change(
        job,
        JobStatus.completed,
        actor,
        message="Replaced the failed washer and confirmed the tap is no longer leaking",
        responsibility_stage=ResponsibilityStage.execution,
    )

    assert completion_event is not None
    assert completion_event.owner_scope == "user"
    assert completion_event.responsibility_owner == ResponsibilityOwner.resident


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


def test_assignment_projection_uses_event_name_snapshots_when_live_relations_drift() -> None:
    event_org_id = uuid.uuid4()
    contractor_user_id = uuid.uuid4()
    job = StubJob(
        status=JobStatus.assigned,
        assigned_org_id=event_org_id,
        assigned_contractor_user_id=contractor_user_id,
        assigned_org=StubAssignee(name="Renamed Plumbing Pty Ltd"),
        assigned_contractor=StubAssignee(name="Renamed Devon"),
        events=[
            StubAssignmentEvent(
                id=uuid.uuid4(),
                created_at=datetime(2026, 4, 4, 10, 0, tzinfo=timezone.utc),
                target_status=None,
                event_type=EventType.assignment,
                assigned_org_id=event_org_id,
                assigned_org_name_snapshot="Newcastle Plumbing",
                assigned_contractor_user_id=contractor_user_id,
                assigned_contractor_name_snapshot="Devon Contractor",
            )
        ],
    )

    assignment = derive_assignment_projection(job, job.events)

    assert assignment.assigned_org_name == "Newcastle Plumbing"
    assert assignment.assigned_contractor_name == "Devon Contractor"
    assert assignment.assignee_scope == "user"
    assert assignment.assignee_label == "Devon Contractor"


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
    assert projection.latest_lifecycle_event_type == "status_change"
    assert projection.responsibility_owner == "coordinator"


def test_coordination_projection_keeps_scheduled_detail_tied_to_schedule_event_after_note() -> None:
    job = StubJob(
        status=JobStatus.scheduled,
        assigned_org_id=uuid.uuid4(),
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
    assert projection.owner_label == "Property manager"
    assert projection.action_required_by == "Newcastle Plumbing"
    assert projection.latest_event_type == "note"
    assert projection.latest_lifecycle_event_type == "schedule"


def test_coordination_projection_keeps_scheduled_state_anchor_when_contractor_claims_field_ownership_before_attendance() -> None:
    student_living = type("Org", (), {"name": "Student Living"})()
    plumbing = type("Org", (), {"name": "Newcastle Plumbing"})()
    triage = type(
        "Actor",
        (),
        {"role": UserRole.triage_officer, "name": "Priya Property Manager", "organisation": student_living},
    )()
    contractor = type(
        "Actor",
        (),
        {"role": UserRole.contractor, "name": "Devon Contractor", "organisation": plumbing},
    )()
    schedule_event = StubEvent(
        id=uuid.uuid4(),
        created_at=datetime(2026, 4, 4, 10, 0, tzinfo=timezone.utc),
        target_status=JobStatus.scheduled,
        event_type=EventType.schedule,
        message="Resident approved Friday morning access window",
        responsibility_stage=ResponsibilityStage.coordination,
        responsibility_owner=ResponsibilityOwner.triage_officer,
    )
    schedule_event.actor_user = triage
    field_owner_event = StubAssignmentEvent(
        id=uuid.uuid4(),
        created_at=datetime(2026, 4, 4, 11, 0, tzinfo=timezone.utc),
        target_status=None,
        event_type=EventType.assignment,
        message="Devon Contractor took field ownership for Newcastle Plumbing",
        responsibility_stage=ResponsibilityStage.execution,
        owner_scope=OwnerScope.user,
        responsibility_owner=ResponsibilityOwner.contractor,
        assigned_org_id=uuid.uuid4(),
        assigned_org=StubAssignee(name="Newcastle Plumbing"),
        assigned_contractor_user_id=uuid.uuid4(),
        assigned_contractor=StubAssignee(name="Devon Contractor"),
    )
    field_owner_event.actor_user = contractor
    note_event = StubEvent(
        id=uuid.uuid4(),
        created_at=datetime(2026, 4, 4, 12, 0, tzinfo=timezone.utc),
        target_status=None,
        event_type=EventType.note,
        message="Confirmed van booking and key collection path for Friday morning.",
    )
    note_event.actor_user = contractor
    job = StubJob(
        status=JobStatus.scheduled,
        assigned_org=StubAssignee(name="Newcastle Plumbing"),
        assigned_contractor=StubAssignee(name="Devon Contractor"),
        events=[schedule_event, field_owner_event, note_event],
    )

    projection = derive_coordination_projection(job, job.events)

    assert projection.status == JobStatus.scheduled
    assert projection.headline == "Visit scheduled; waiting for contractor attendance"
    assert projection.owner_label == "Property manager"
    assert projection.action_required_by == "Devon Contractor"
    assert projection.responsibility_owner == "triage_officer"
    assert projection.latest_event_type == "note"
    assert projection.latest_lifecycle_event_type == "schedule"


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
    assert projection.latest_lifecycle_event_type == "completion"


def test_assignment_projection_clears_current_assignee_after_explicit_assignment_end_event() -> None:
    job = StubJob(
        status=JobStatus.completed,
        assigned_org_id=uuid.uuid4(),
        assigned_org=StubAssignee(name="Drifted Row Org"),
        events=[
            StubAssignmentEvent(
                id=uuid.uuid4(),
                created_at=datetime(2026, 3, 21, 10, 0, tzinfo=timezone.utc),
                target_status=None,
                event_type=EventType.assignment,
                message="Assigned Newcastle Plumbing",
                assigned_org_id=uuid.uuid4(),
                assigned_org_name_snapshot="Newcastle Plumbing",
            ),
            StubAssignmentEvent(
                id=uuid.uuid4(),
                created_at=datetime(2026, 3, 21, 11, 0, tzinfo=timezone.utc),
                target_status=None,
                event_type=EventType.assignment,
                message="Assignment cleared",
                assigned_org_id=None,
                assigned_contractor_user_id=None,
            ),
            StubEvent(
                id=uuid.uuid4(),
                created_at=datetime(2026, 3, 21, 12, 0, tzinfo=timezone.utc),
                target_status=JobStatus.completed,
                event_type=EventType.completion,
                message="Tap washer replaced and sink tested with no further leak",
                responsibility_stage=ResponsibilityStage.execution,
            ),
        ],
    )

    assignment = derive_assignment_projection(job, job.events)
    projection = derive_coordination_projection(job, job.events)

    assert assignment.assigned_org_id is None
    assert assignment.assignee_label is None
    assert projection.status == JobStatus.completed
    assert projection.headline == "Work marked complete"
    assert projection.latest_event_type == "completion"
    assert projection.latest_lifecycle_event_type == "completion"


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
                responsibility_stage=ResponsibilityStage.coordination,
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
    assert projection.responsibility_stage == "coordination"


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


def test_visit_plan_projection_flags_resident_access_note_newer_than_booking() -> None:
    student_living = type("Org", (), {"name": "Student Living"})()
    resident = type(
        "Actor",
        (),
        {"role": UserRole.resident, "name": "Riley Resident", "organisation": student_living},
    )()
    triage = type(
        "Actor",
        (),
        {"role": UserRole.triage_officer, "name": "Priya Property Manager", "organisation": student_living},
    )()
    schedule_event = StubEvent(
        id=uuid.uuid4(),
        created_at=datetime(2026, 4, 4, 10, 0, tzinfo=timezone.utc),
        target_status=JobStatus.scheduled,
        event_type=EventType.schedule,
        message="Booked plumber for Friday 14:00-16:00 after the original resident access confirmation",
        responsibility_stage=ResponsibilityStage.coordination,
    )
    schedule_event.actor_user = triage
    access_event = StubEvent(
        id=uuid.uuid4(),
        created_at=datetime(2026, 4, 4, 11, 0, tzinfo=timezone.utc),
        target_status=None,
        event_type=EventType.note,
        message="Please avoid 3pm because the room is locked for a welfare check.",
        reason_code="resident_access_update",
        responsibility_stage=ResponsibilityStage.coordination,
    )
    access_event.actor_user = resident
    job = StubJob(status=JobStatus.scheduled, events=[schedule_event, access_event])

    plan = derive_visit_plan(job, job.events)

    assert plan is not None
    assert plan.headline == "Resident access note is newer than the booked visit"
    assert plan.dispatch_message is None
    assert plan.booking_message == schedule_event.message
    assert plan.access_message == access_event.message
    assert plan.access_actor_label == "Riley Resident (Student Living)"


def test_visit_plan_projection_keeps_access_blocker_visible_after_failed_attendance() -> None:
    student_living = type("Org", (), {"name": "Student Living"})()
    plumbing = type("Org", (), {"name": "Newcastle Plumbing"})()
    triage = type(
        "Actor",
        (),
        {"role": UserRole.triage_officer, "name": "Priya Property Manager", "organisation": student_living},
    )()
    contractor = type(
        "Actor",
        (),
        {"role": UserRole.contractor, "name": "Devon Contractor", "organisation": plumbing},
    )()
    schedule_event = StubEvent(
        id=uuid.uuid4(),
        created_at=datetime(2026, 4, 4, 9, 0, tzinfo=timezone.utc),
        target_status=JobStatus.scheduled,
        event_type=EventType.schedule,
        message="Booked plumber for Wednesday morning with plant room key collection at reception",
        responsibility_stage=ResponsibilityStage.coordination,
    )
    schedule_event.actor_user = triage
    blocked_event = StubEvent(
        id=uuid.uuid4(),
        created_at=datetime(2026, 4, 4, 12, 0, tzinfo=timezone.utc),
        target_status=JobStatus.blocked,
        event_type=EventType.status_change,
        message="Arrived on site but the plant room was locked and no key handoff was arranged.",
        reason_code="no_access",
        responsibility_stage=ResponsibilityStage.execution,
    )
    blocked_event.actor_user = contractor
    job = StubJob(status=JobStatus.blocked, events=[schedule_event, blocked_event])

    plan = derive_visit_plan(job, job.events)

    assert plan is not None
    assert plan.headline == "Access arrangement is not ready for the next visit"
    assert plan.dispatch_message is None
    assert plan.blocker_message == blocked_event.message
    assert plan.blocker_actor_label == "Devon Contractor (Newcastle Plumbing)"


def test_visit_plan_projection_flags_booked_visit_without_named_attendee() -> None:
    student_living = type("Org", (), {"name": "Student Living"})()
    triage = type(
        "Actor",
        (),
        {"role": UserRole.triage_officer, "name": "Priya Property Manager", "organisation": student_living},
    )()
    coordinator = type(
        "Actor",
        (),
        {"role": UserRole.coordinator, "name": "Casey Dispatch Coordinator", "organisation": student_living},
    )()
    assigned_org = StubAssignee(name="Newcastle Plumbing")
    assignment_event = StubAssignmentEvent(
        id=uuid.uuid4(),
        created_at=datetime(2026, 4, 4, 9, 0, tzinfo=timezone.utc),
        target_status=None,
        event_type=EventType.assignment,
        message="Assigned Newcastle Plumbing",
        assigned_org_id=uuid.uuid4(),
        assigned_org=assigned_org,
    )
    assignment_event.actor_user = coordinator
    schedule_event = StubEvent(
        id=uuid.uuid4(),
        created_at=datetime(2026, 4, 4, 10, 0, tzinfo=timezone.utc),
        target_status=JobStatus.scheduled,
        event_type=EventType.schedule,
        message="Booked plumber for Friday 14:00-16:00",
        responsibility_stage=ResponsibilityStage.coordination,
    )
    schedule_event.actor_user = triage
    job = StubJob(
        status=JobStatus.scheduled,
        events=[assignment_event, schedule_event],
        assigned_org_id=assignment_event.assigned_org_id,
        assigned_org=assigned_org,
    )

    plan = derive_visit_plan(job, job.events)

    assert plan is not None
    assert plan.headline == "Booked visit is waiting on contractor acknowledgement"
    assert (
        plan.summary
        == "The visit window is recorded, but the dispatched contractor organisation has not confirmed the "
        "booking in the shared timeline yet."
    )
    assert plan.dispatch_message == "Assigned Newcastle Plumbing"
    assert plan.dispatch_actor_label == "Casey Dispatch Coordinator (Student Living)"
    assert plan.booking_message == "Booked plumber for Friday 14:00-16:00"


def test_visit_plan_projection_returns_to_current_plan_after_contractor_acknowledges_booking() -> None:
    student_living = type("Org", (), {"name": "Student Living"})()
    plumbing = type("Org", (), {"name": "Newcastle Plumbing"})()
    triage = type(
        "Actor",
        (),
        {"role": UserRole.triage_officer, "name": "Priya Property Manager", "organisation": student_living},
    )()
    coordinator = type(
        "Actor",
        (),
        {"role": UserRole.coordinator, "name": "Casey Dispatch Coordinator", "organisation": student_living},
    )()
    contractor = type(
        "Actor",
        (),
        {"role": UserRole.contractor, "name": "Devon Contractor", "organisation": plumbing},
    )()
    assigned_org = StubAssignee(name="Newcastle Plumbing")
    assignment_event = StubAssignmentEvent(
        id=uuid.uuid4(),
        created_at=datetime(2026, 4, 4, 9, 0, tzinfo=timezone.utc),
        target_status=None,
        event_type=EventType.assignment,
        message="Assigned Newcastle Plumbing",
        assigned_org_id=uuid.uuid4(),
        assigned_org=assigned_org,
    )
    assignment_event.actor_user = coordinator
    schedule_event = StubEvent(
        id=uuid.uuid4(),
        created_at=datetime(2026, 4, 4, 10, 0, tzinfo=timezone.utc),
        target_status=JobStatus.scheduled,
        event_type=EventType.schedule,
        message="Booked plumber for Friday 14:00-16:00",
        responsibility_stage=ResponsibilityStage.coordination,
    )
    schedule_event.actor_user = triage
    contractor_note = StubEvent(
        id=uuid.uuid4(),
        created_at=datetime(2026, 4, 4, 11, 0, tzinfo=timezone.utc),
        target_status=None,
        event_type=EventType.note,
        message="Confirmed van booking and key collection path for Friday morning.",
    )
    contractor_note.actor_user = contractor
    job = StubJob(
        status=JobStatus.scheduled,
        events=[assignment_event, schedule_event, contractor_note],
        assigned_org_id=assignment_event.assigned_org_id,
        assigned_org=assigned_org,
    )

    plan = derive_visit_plan(job, job.events)

    assert plan is not None
    assert plan.headline == "Current visit plan is recorded"
    assert (
        plan.summary
        == "Use the booked window and contractor organisation as the working attendance plan. "
        "A named field worker can be added later if operations actually know it."
    )


def test_visit_plan_projection_flags_dispatch_without_booked_visit() -> None:
    student_living = type("Org", (), {"name": "Student Living"})()
    coordinator = type(
        "Actor",
        (),
        {"role": UserRole.coordinator, "name": "Casey Dispatch Coordinator", "organisation": student_living},
    )()
    assigned_org = StubAssignee(name="Campus Maintenance")
    assignment_event = StubAssignmentEvent(
        id=uuid.uuid4(),
        created_at=datetime(2026, 4, 4, 9, 0, tzinfo=timezone.utc),
        target_status=None,
        event_type=EventType.assignment,
        message="Assigned Campus Maintenance",
        assigned_org_id=uuid.uuid4(),
        assigned_org=assigned_org,
    )
    assignment_event.actor_user = coordinator
    triage_event = StubEvent(
        id=uuid.uuid4(),
        created_at=datetime(2026, 4, 4, 10, 0, tzinfo=timezone.utc),
        target_status=JobStatus.triaged,
        event_type=EventType.status_change,
        message="Repeat heater issue reviewed and ready to book",
        responsibility_stage=ResponsibilityStage.triage,
    )
    triage_event.actor_user = type(
        "Actor",
        (),
        {"role": UserRole.triage_officer, "name": "Priya Property Manager", "organisation": student_living},
    )()
    job = StubJob(
        status=JobStatus.triaged,
        events=[assignment_event, triage_event],
        assigned_org_id=assignment_event.assigned_org_id,
        assigned_org=assigned_org,
    )

    plan = derive_visit_plan(job, job.events)

    assert plan is not None
    assert plan.headline == "Dispatch recorded but attendance still needs a booked visit"
    assert plan.summary == "The work has a dispatch target, but the resident-visible visit window has not been recorded yet."
    assert plan.dispatch_message == "Assigned Campus Maintenance"
    assert plan.dispatch_actor_label == "Casey Dispatch Coordinator (Student Living)"


def test_build_focus_counts_surfaces_response_visit_and_repeat_risk() -> None:
    counts = build_focus_counts(
        [
            {
                "status": "blocked",
                "pending_signal_at": datetime(2026, 4, 4, 8, 0, tzinfo=timezone.utc),
                "pending_signal_owner_role": "coordinator",
                "visit_plan_headline": "Access arrangement is not ready for the next visit",
                "operational_history_open_job_count": 2,
            },
            {
                "status": "triaged",
                "pending_signal_at": None,
                "visit_plan_headline": "Attendance still needs a booked visit",
                "operational_history_open_job_count": 0,
            },
            {
                "status": "triaged",
                "pending_signal_at": None,
                "visit_plan_headline": "Dispatch recorded but attendance still needs a booked visit",
                "operational_history_open_job_count": 0,
            },
            {
                "status": "scheduled",
                "pending_signal_at": None,
                "visit_plan_headline": "Visit is booked but no dispatch target is recorded",
                "operational_history_open_job_count": 0,
            },
            {
                "status": "completed",
                "pending_signal_at": None,
                "visit_plan_headline": "Current visit plan is recorded",
                "operational_history_open_job_count": 1,
            },
        ]
    )

    assert counts == {
        "response_needed": 1,
        "state_gap": 0,
        "visit_attention": 4,
        "repeat_open_work": 2,
        "blocked": 1,
    }


def test_build_focus_counts_limits_response_needed_to_the_viewing_role() -> None:
    jobs = [
        {
            "status": "scheduled",
            "pending_signal_at": datetime(2026, 4, 4, 9, 0, tzinfo=timezone.utc),
            "pending_signal_owner_role": "coordinator",
            "visit_plan_headline": "Resident access note is newer than the booked visit",
            "operational_history_open_job_count": 0,
        },
        {
            "status": "completed",
            "pending_signal_at": datetime(2026, 4, 4, 10, 0, tzinfo=timezone.utc),
            "pending_signal_owner_role": "resident",
            "visit_plan_headline": "Current visit plan is recorded",
            "operational_history_open_job_count": 0,
        },
    ]

    coordinator_counts = build_focus_counts(jobs, user=StubActor(role=UserRole.coordinator))
    resident_counts = build_focus_counts(jobs, user=StubActor(role=UserRole.resident))
    contractor_counts = build_focus_counts(jobs, user=StubActor(role=UserRole.contractor))

    assert coordinator_counts["response_needed"] == 1
    assert resident_counts["response_needed"] == 1
    assert contractor_counts["response_needed"] == 0


def test_derive_viewer_guidance_translates_operations_owned_next_step_for_resident() -> None:
    guidance = derive_viewer_guidance(
        {
            "status": "scheduled",
            "coordination_owner_label": "Dispatch coordinator",
            "visit_plan_summary": "Apply the resident access change to the booking before the next attendance.",
            "pending_signal_at": datetime(2026, 4, 4, 9, 0, tzinfo=timezone.utc),
            "pending_signal_owner_role": "coordinator",
        },
        user=StubActor(role=UserRole.resident),
    )

    assert guidance.headline == "Dispatch coordinator is carrying the next step"
    assert guidance.summary == "Apply the resident access change to the booking before the next attendance."


def test_derive_viewer_guidance_keeps_scheduled_contractor_focused_on_shared_booking() -> None:
    guidance = derive_viewer_guidance(
        {
            "status": "scheduled",
            "visit_plan_summary": "Use the booked window and latest access note as the working attendance plan.",
            "pending_signal_at": None,
        },
        user=StubActor(role=UserRole.contractor),
    )

    assert guidance.headline == "Use the shared booking before attending site"
    assert guidance.summary == "Use the booked window and latest access note as the working attendance plan."


def test_derive_viewer_guidance_tells_operations_completed_work_is_waiting_on_resident_truth_signal() -> None:
    guidance = derive_viewer_guidance(
        {
            "status": "completed",
            "responsibility_owner": "resident",
            "pending_signal_at": None,
        },
        user=StubActor(role=UserRole.triage_officer),
    )

    assert guidance.headline == "Resident confirmation is the next outcome signal"
    assert guidance.summary == (
        "Wait for the resident confirmation, recurrence, or charge response before treating the job as fully closed."
    )


def test_derive_queue_priority_prefers_blocked_and_response_signals_over_generic_recency() -> None:
    blocked_priority = derive_queue_priority(
        {
            "status": "blocked",
            "pending_signal_at": datetime(2026, 4, 4, 8, 0, tzinfo=timezone.utc),
            "pending_signal_headline": "Resident access detail needs operations follow-through",
            "visit_plan_headline": "Access arrangement is not ready for the next visit",
            "operational_history_open_job_count": 2,
        }
    )
    response_priority = derive_queue_priority(
        {
            "status": "scheduled",
            "pending_signal_at": datetime(2026, 4, 4, 9, 0, tzinfo=timezone.utc),
            "pending_signal_headline": "Resident access detail needs operations follow-through",
            "visit_plan_headline": "Resident access note is newer than the booked visit",
            "operational_history_open_job_count": 0,
        }
    )
    repeat_priority = derive_queue_priority(
        {
            "status": "triaged",
            "pending_signal_at": None,
            "visit_plan_headline": "Current visit plan is recorded",
            "operational_history_open_job_count": 2,
            "operational_history_headline": "Repeat issue risk on this asset",
        }
    )

    assert blocked_priority.label == "Blocked coordination"
    assert blocked_priority.rank < response_priority.rank < repeat_priority.rank
    assert response_priority.summary == "Resident access detail needs operations follow-through"
    assert repeat_priority.label == "Repeat work still open"


def test_derive_queue_priority_only_marks_response_as_owned_for_the_target_role() -> None:
    job = {
        "status": "scheduled",
        "pending_signal_at": datetime(2026, 4, 4, 9, 0, tzinfo=timezone.utc),
        "pending_signal_owner_role": "coordinator",
        "pending_signal_headline": "Resident access detail needs operations follow-through",
        "visit_plan_headline": "Resident access note is newer than the booked visit",
        "operational_history_open_job_count": 0,
    }

    coordinator_priority = derive_queue_priority(job, user=StubActor(role=UserRole.coordinator))
    resident_priority = derive_queue_priority(job, user=StubActor(role=UserRole.resident))

    assert coordinator_priority.label == "Waiting on response"
    assert resident_priority.label == "Visit plan at risk"
    assert resident_priority.summary == "Resident access note is newer than the booked visit"


def test_derive_queue_priority_treats_missing_booking_and_missing_dispatch_as_visit_attention() -> None:
    missing_booking_priority = derive_queue_priority(
        {
            "status": "triaged",
            "pending_signal_at": None,
            "visit_plan_headline": "Dispatch recorded but attendance still needs a booked visit",
            "operational_history_open_job_count": 0,
        }
    )
    missing_dispatch_priority = derive_queue_priority(
        {
            "status": "scheduled",
            "pending_signal_at": None,
            "visit_plan_headline": "Visit is booked but no dispatch target is recorded",
            "operational_history_open_job_count": 0,
        }
    )
    missing_ack_priority = derive_queue_priority(
        {
            "status": "scheduled",
            "pending_signal_at": None,
            "visit_plan_headline": "Booked visit is waiting on contractor acknowledgement",
            "operational_history_open_job_count": 0,
        }
    )

    assert missing_booking_priority.label == "Visit plan at risk"
    assert missing_booking_priority.summary == "Dispatch recorded but attendance still needs a booked visit"
    assert missing_booking_priority.rank == 2

    assert missing_dispatch_priority.label == "Visit plan at risk"
    assert missing_dispatch_priority.summary == "Visit is booked but no dispatch target is recorded"
    assert missing_dispatch_priority.rank == 2

    assert missing_ack_priority.label == "Visit plan at risk"
    assert missing_ack_priority.summary == "Booked visit is waiting on contractor acknowledgement"
    assert missing_ack_priority.rank == 2


def test_derive_queue_priority_prefers_repeat_open_work_over_generic_unplanned_attendance() -> None:
    priority = derive_queue_priority(
        {
            "status": "new",
            "pending_signal_at": None,
            "visit_plan_headline": "Attendance planning not recorded yet",
            "operational_history_open_job_count": 2,
            "operational_history_headline": "Repeat issue risk on this asset",
        }
    )

    assert priority.label == "Repeat work still open"
    assert priority.summary == "Repeat issue risk on this asset"
    assert priority.rank == 3


def test_sort_jobs_for_queue_puts_response_and_repeat_risk_ahead_of_recent_activity() -> None:
    jobs = sort_jobs_for_queue(
        [
            {
                "id": uuid.uuid4(),
                "title": "Routine recent note",
                "queue_priority_rank": 5,
                "latest_event_at": datetime(2026, 4, 4, 12, 0, tzinfo=timezone.utc),
                "latest_lifecycle_event_at": datetime(2026, 4, 4, 11, 0, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 4, 4, 12, 0, tzinfo=timezone.utc),
                "created_at": datetime(2026, 4, 4, 10, 0, tzinfo=timezone.utc),
            },
            {
                "id": uuid.uuid4(),
                "title": "Repeat leak still active",
                "queue_priority_rank": 3,
                "latest_event_at": datetime(2026, 4, 4, 9, 0, tzinfo=timezone.utc),
                "latest_lifecycle_event_at": datetime(2026, 4, 4, 9, 0, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 4, 4, 9, 0, tzinfo=timezone.utc),
                "created_at": datetime(2026, 4, 4, 8, 0, tzinfo=timezone.utc),
            },
            {
                "id": uuid.uuid4(),
                "title": "Resident access reply needed",
                "queue_priority_rank": 1,
                "latest_event_at": datetime(2026, 4, 4, 8, 0, tzinfo=timezone.utc),
                "latest_lifecycle_event_at": datetime(2026, 4, 4, 7, 0, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 4, 4, 8, 0, tzinfo=timezone.utc),
                "created_at": datetime(2026, 4, 4, 6, 0, tzinfo=timezone.utc),
            },
        ]
    )

    assert [job["title"] for job in jobs] == [
        "Resident access reply needed",
        "Repeat leak still active",
        "Routine recent note",
    ]


def test_coordination_projection_treats_resident_resolution_confirmation_as_truthful_completion_signal() -> None:
    student_living = type("Org", (), {"name": "Student Living"})()
    resident = type(
        "Actor",
        (),
        {"role": UserRole.resident, "name": "Riley Resident", "organisation": student_living},
    )()
    completion_event = StubEvent(
        id=uuid.uuid4(),
        created_at=datetime(2026, 4, 4, 9, 0, tzinfo=timezone.utc),
        target_status=JobStatus.completed,
        event_type=EventType.completion,
        message="Replaced the cartridge and pressure-tested the line with no further leak",
        responsibility_stage=ResponsibilityStage.execution,
    )
    resolution_event = StubEvent(
        id=uuid.uuid4(),
        created_at=datetime(2026, 4, 4, 11, 0, tzinfo=timezone.utc),
        target_status=None,
        event_type=EventType.note,
        message="The shower has stayed dry since yesterday's repair.",
        reason_code="resident_confirmed_resolved",
        responsibility_stage=ResponsibilityStage.execution,
        responsibility_owner=ResponsibilityOwner.resident,
    )
    resolution_event.actor_user = resident
    job = StubJob(status=JobStatus.completed, events=[completion_event, resolution_event])

    projection = derive_coordination_projection(job, job.events)

    assert projection.status == JobStatus.completed
    assert projection.headline == "Resident confirmed the issue is resolved after the visit"
    assert projection.detail == "The shower has stayed dry since yesterday's repair."
    assert projection.owner_label == "Resident"


def test_coordination_projection_treats_charge_notice_as_resident_accountability_signal() -> None:
    student_living = type("Org", (), {"name": "Student Living"})()
    triage = type(
        "Actor",
        (),
        {"role": UserRole.triage_officer, "name": "Priya Property Manager", "organisation": student_living},
    )()
    completion_event = StubEvent(
        id=uuid.uuid4(),
        created_at=datetime(2026, 4, 4, 9, 0, tzinfo=timezone.utc),
        target_status=JobStatus.completed,
        event_type=EventType.completion,
        message="Replaced the damaged mixer and confirmed the shower was watertight on departure.",
        responsibility_stage=ResponsibilityStage.execution,
    )
    notice_event = StubEvent(
        id=uuid.uuid4(),
        created_at=datetime(2026, 4, 4, 11, 0, tzinfo=timezone.utc),
        target_status=None,
        event_type=EventType.note,
        message="Recorded the resident-liable damage outcome and issued the charge notice through the portal.",
        reason_code="charge_notice_issued",
        responsibility_stage=ResponsibilityStage.coordination,
        responsibility_owner=ResponsibilityOwner.resident,
    )
    notice_event.actor_user = triage
    job = StubJob(status=JobStatus.completed, events=[completion_event, notice_event])

    projection = derive_coordination_projection(job, job.events)
    signal = derive_pending_signal(job, job.events)

    assert projection.status == JobStatus.completed
    assert projection.headline == "Post-visit charge notice recorded"
    assert projection.detail == "Recorded the resident-liable damage outcome and issued the charge notice through the portal."
    assert projection.owner_label == "Resident"
    assert signal is not None
    assert signal.headline == "Post-visit charge notice needs resident review"
    assert signal.owner_role == "resident"
    assert signal.owner_label == "Resident"


def test_coordination_projection_treats_resident_charge_appeal_as_operations_signal() -> None:
    student_living = type("Org", (), {"name": "Student Living"})()
    resident = type(
        "Actor",
        (),
        {"role": UserRole.resident, "name": "Riley Resident", "organisation": student_living},
    )()
    triage = type(
        "Actor",
        (),
        {"role": UserRole.triage_officer, "name": "Priya Property Manager", "organisation": student_living},
    )()
    completion_event = StubEvent(
        id=uuid.uuid4(),
        created_at=datetime(2026, 4, 4, 9, 0, tzinfo=timezone.utc),
        target_status=JobStatus.completed,
        event_type=EventType.completion,
        message="Replaced the damaged mixer and confirmed the shower was watertight on departure.",
        responsibility_stage=ResponsibilityStage.execution,
    )
    notice_event = StubEvent(
        id=uuid.uuid4(),
        created_at=datetime(2026, 4, 4, 10, 0, tzinfo=timezone.utc),
        target_status=None,
        event_type=EventType.note,
        message="Recorded the resident-liable damage outcome and issued the charge notice through the portal.",
        reason_code="charge_notice_issued",
        responsibility_stage=ResponsibilityStage.coordination,
        responsibility_owner=ResponsibilityOwner.resident,
    )
    notice_event.actor_user = triage
    appeal_event = StubEvent(
        id=uuid.uuid4(),
        created_at=datetime(2026, 4, 4, 11, 0, tzinfo=timezone.utc),
        target_status=None,
        event_type=EventType.note,
        message="I dispute the charge because the mixer failed again after the first contractor visit.",
        reason_code="charge_appeal_submitted",
        responsibility_stage=ResponsibilityStage.triage,
        responsibility_owner=ResponsibilityOwner.triage_officer,
    )
    appeal_event.actor_user = resident
    job = StubJob(status=JobStatus.completed, events=[completion_event, notice_event, appeal_event])

    projection = derive_coordination_projection(job, job.events)
    signal = derive_pending_signal(job, job.events)

    assert projection.status == JobStatus.completed
    assert projection.headline == "Resident disputed the post-visit charge"
    assert projection.detail == "I dispute the charge because the mixer failed again after the first contractor visit."
    assert projection.owner_label == "Property manager"
    assert signal is not None
    assert signal.headline == "Resident disputed the post-visit charge"
    assert signal.owner_role == "triage_officer"
    assert signal.owner_label == "Property manager"


def test_coordination_projection_labels_after_hours_handoff_signal_explicitly() -> None:
    student_living = type("Org", (), {"name": "Student Living"})()
    reception = type(
        "Actor",
        (),
        {"role": UserRole.reception_admin, "name": "Fran Front Desk", "organisation": student_living},
    )()
    report_event = StubEvent(
        id=uuid.uuid4(),
        created_at=datetime(2026, 4, 4, 9, 0, tzinfo=timezone.utc),
        target_status=JobStatus.new,
        event_type=EventType.report_created,
        message="Resident reported a leaking sink through the after-hours line.",
        responsibility_stage=ResponsibilityStage.reception,
    )
    handoff_event = StubEvent(
        id=uuid.uuid4(),
        created_at=datetime(2026, 4, 4, 10, 0, tzinfo=timezone.utc),
        target_status=None,
        event_type=EventType.note,
        message="Daytime Student Living services acknowledged the overnight handoff and queued the first callback.",
        reason_code="after_hours_handoff_received",
        responsibility_stage=ResponsibilityStage.reception,
        responsibility_owner=ResponsibilityOwner.reception_admin,
    )
    handoff_event.actor_user = reception
    job = StubJob(status=JobStatus.new, events=[report_event, handoff_event])

    projection = derive_coordination_projection(job, job.events)

    assert projection.status == JobStatus.new
    assert projection.headline == "After-hours handoff received for daytime follow-through"
    assert projection.detail == "Daytime Student Living services acknowledged the overnight handoff and queued the first callback."
    assert projection.owner_label == "Front desk"


def test_latest_role_update_prefers_event_snapshots_when_live_actor_labels_drift() -> None:
    renamed_org = type("Org", (), {"name": "Renamed Student Living"})()
    renamed_actor = type(
        "Actor",
        (),
        {"role": UserRole.coordinator, "name": "Renamed Casey", "organisation": renamed_org},
    )()
    event = StubEvent(
        id=uuid.uuid4(),
        created_at=datetime(2026, 4, 4, 12, 0, tzinfo=timezone.utc),
        target_status=None,
        event_type=EventType.note,
        message="Resident asked for a different key handoff point",
        reason_code="resident_access_update",
        responsibility_stage=ResponsibilityStage.coordination,
        responsibility_owner=ResponsibilityOwner.coordinator,
    )
    event.actor_user = renamed_actor
    event.actor_name_snapshot = "Casey Dispatch Coordinator"
    event.actor_role_snapshot = "coordinator"
    event.actor_org_name_snapshot = "Student Living"

    update = latest_role_update(events=[event], roles={UserRole.coordinator.value})

    assert update is not None
    assert update.actor_label == "Casey Dispatch Coordinator (Student Living)"
    assert update.actor_role == "coordinator"


def test_pending_signal_uses_snapshot_backed_actor_label_after_live_rename_drift() -> None:
    tenant_org = type("Org", (), {"name": "Renamed Student Living"})()
    resident = type(
        "Actor",
        (),
        {"role": UserRole.resident, "name": "Renamed Riley", "organisation": tenant_org},
    )()
    operations = type(
        "Actor",
        (),
        {"role": UserRole.coordinator, "name": "Casey Dispatch Coordinator", "organisation": tenant_org},
    )()
    operations_event = StubEvent(
        id=uuid.uuid4(),
        created_at=datetime(2026, 4, 4, 10, 0, tzinfo=timezone.utc),
        target_status=JobStatus.scheduled,
        event_type=EventType.schedule,
        message="Booked plumber for Friday 14:00-16:00",
        responsibility_stage=ResponsibilityStage.coordination,
        responsibility_owner=ResponsibilityOwner.contractor,
    )
    operations_event.actor_user = operations
    resident_event = StubEvent(
        id=uuid.uuid4(),
        created_at=datetime(2026, 4, 4, 11, 0, tzinfo=timezone.utc),
        target_status=None,
        event_type=EventType.note,
        message="Please collect the spare key from reception instead.",
        reason_code="resident_access_update",
        responsibility_stage=ResponsibilityStage.coordination,
        responsibility_owner=ResponsibilityOwner.coordinator,
    )
    resident_event.actor_user = resident
    resident_event.actor_name_snapshot = "Riley Resident"
    resident_event.actor_role_snapshot = "resident"
    resident_event.actor_org_name_snapshot = "Student Living"
    job = StubJob(status=JobStatus.scheduled, events=[operations_event, resident_event])

    signal = derive_pending_signal(job, job.events)

    assert signal is not None
    assert signal.actor_label == "Riley Resident (Student Living)"
    assert signal.actor_role == "resident"
    assert signal.owner_role == "coordinator"
    assert signal.owner_label == "Dispatch coordinator"


def test_visit_plan_uses_snapshot_backed_resident_role_when_live_actor_relation_is_missing() -> None:
    triage_org = type("Org", (), {"name": "Student Living"})()
    triage = type(
        "Actor",
        (),
        {"role": UserRole.triage_officer, "name": "Priya Property Manager", "organisation": triage_org},
    )()
    schedule_event = StubEvent(
        id=uuid.uuid4(),
        created_at=datetime(2026, 4, 4, 10, 0, tzinfo=timezone.utc),
        target_status=JobStatus.scheduled,
        event_type=EventType.schedule,
        message="Booked plumber for Friday morning attendance",
        responsibility_stage=ResponsibilityStage.coordination,
    )
    schedule_event.actor_user = triage
    access_event = StubEvent(
        id=uuid.uuid4(),
        created_at=datetime(2026, 4, 4, 11, 0, tzinfo=timezone.utc),
        target_status=None,
        event_type=EventType.note,
        message="Please avoid 3pm because the room is locked for a welfare check.",
        reason_code="resident_access_update",
        responsibility_stage=ResponsibilityStage.coordination,
    )
    access_event.actor_name_snapshot = "Riley Resident"
    access_event.actor_role_snapshot = "resident"
    access_event.actor_org_name_snapshot = "Student Living"
    job = StubJob(status=JobStatus.scheduled, events=[schedule_event, access_event])

    plan = derive_visit_plan(job, job.events)

    assert plan is not None
    assert plan.headline == "Resident access note is newer than the booked visit"
    assert plan.access_actor_label == "Riley Resident (Student Living)"
