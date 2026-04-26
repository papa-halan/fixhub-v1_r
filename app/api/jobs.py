from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import (
    clean_text,
    contractor_has_current_assignment,
    get_current_user,
    get_session,
    serialize_event,
    serialize_job_for_user,
    serialize_job_with_history,
    serialize_user,
    visible_events,
    visible_job,
    visible_jobs,
)
from app.models import (
    EventType,
    Job,
    JobStatus,
    Location,
    OwnerScope,
    Organisation,
    OrganisationType,
    ReportChannel,
    ResidentUpdateReason,
    ResponsibilityOwner,
    ResponsibilityStage,
    User,
    UserRole,
)
from app.schema import EventCreate, EventRead, JobCreate, JobRead, JobUpdate, ResidentUpdateCreate, UserRead
from app.services.catalog import is_reportable_location, location_label
from app.services import (
    ALLOWED_STATUS_CHANGES,
    ASSIGNEE_REQUIRED_STATUSES,
    ASSIGNMENT_ROLES,
    MESSAGE_REQUIRED_STATUSES,
    OPERATIONS_ROLES,
    REASON_REQUIRED_STATUSES,
    EventSpec,
    STATUS_EVENT_MESSAGES,
    append_event,
    apply_status_change,
    assignee_label,
    assignee_scope,
    can_user_report_location,
    find_asset_by_name,
    job_has_assignee,
    sync_job_assignment_from_events,
    sync_job_status_from_events,
    validate_assignment_clear_requires_explicit_status,
    validate_assignment_change_requires_explicit_status,
)


router = APIRouter(prefix="/api")

POST_VISIT_RESIDENT_UPDATE_REASONS = {
    ResidentUpdateReason.issue_still_present,
    ResidentUpdateReason.resident_reported_recurrence,
    ResidentUpdateReason.resident_confirmed_resolved,
    ResidentUpdateReason.charge_appeal_submitted,
}
ACTIVE_COORDINATION_RESIDENT_UPDATE_REASONS = {
    ResidentUpdateReason.resident_access_update,
    ResidentUpdateReason.resident_access_issue,
}
POST_VISIT_RESIDENT_UPDATE_STATUSES = {JobStatus.completed, JobStatus.follow_up_scheduled}
ACTIVE_COORDINATION_RESIDENT_UPDATE_BLOCKED_STATUSES = {JobStatus.cancelled, JobStatus.completed}
OPERATIONS_INTAKE_CHANNELS = {
    ReportChannel.staff_created,
    ReportChannel.security_after_hours,
    ReportChannel.inspection_housekeeping,
}
ASSIGNMENT_ENDING_STATUSES = {
    JobStatus.completed,
    JobStatus.cancelled,
    JobStatus.reopened,
}
STATUS_CHANGE_ASSIGNEE_REQUIRED_STATUSES = (
    ASSIGNEE_REQUIRED_STATUSES - {JobStatus.scheduled}
) | {JobStatus.follow_up_scheduled}
CONTRACTOR_FIELD_OWNERSHIP_STATUSES = {
    JobStatus.in_progress,
    JobStatus.blocked,
}
NOTE_REASON_DEFAULTS = {
    "after_hours_handoff_received": (
        ResponsibilityStage.reception,
        OwnerScope.organisation,
        ResponsibilityOwner.reception_admin,
    ),
    "liability_assessed": (
        ResponsibilityStage.triage,
        OwnerScope.organisation,
        ResponsibilityOwner.triage_officer,
    ),
    "charge_notice_issued": (
        ResponsibilityStage.coordination,
        OwnerScope.user,
        ResponsibilityOwner.resident,
    ),
    "charge_resolved": (
        ResponsibilityStage.coordination,
        OwnerScope.organisation,
        ResponsibilityOwner.coordinator,
    ),
}


def report_created_message(*, intake_channel: ReportChannel, current_user: User, reporter: User) -> str:
    if intake_channel == ReportChannel.resident_portal:
        return "Resident reported the issue through the portal."
    if intake_channel == ReportChannel.staff_created:
        return f"{current_user.name} logged this issue on behalf of {reporter.name}."
    if intake_channel == ReportChannel.security_after_hours:
        return f"{current_user.name} logged this issue through the after-hours support path for {reporter.name}."
    return f"{current_user.name} logged this issue from an inspection or housekeeping round."


def validate_resident_update_reason_for_job(*, job: Job, reason_code: ResidentUpdateReason) -> None:
    current_status = sync_job_status_from_events(job)
    if reason_code in POST_VISIT_RESIDENT_UPDATE_REASONS:
        if current_status not in POST_VISIT_RESIDENT_UPDATE_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    "Post-visit resident updates are only allowed after completion or while a follow-up visit "
                    "is already recorded"
                ),
            )
        if (
            reason_code == ResidentUpdateReason.resident_confirmed_resolved
            and current_status != JobStatus.completed
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="resident_confirmed_resolved is only allowed after a completion event",
            )
        return

    if (
        reason_code in ACTIVE_COORDINATION_RESIDENT_UPDATE_REASONS
        and current_status in ACTIVE_COORDINATION_RESIDENT_UPDATE_BLOCKED_STATUSES
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Access updates must be recorded before cancellation or after the job is reopened",
        )


def validate_transition_request(
    *,
    job: Job,
    target_status: JobStatus,
    event_message: str | None,
    reason_code: str | None,
) -> None:
    if target_status == job.status:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Job is already {target_status.value}; omit status or choose a different lifecycle move",
        )
    if target_status in MESSAGE_REQUIRED_STATUSES and event_message is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"event_message is required when moving a job to {target_status.value}",
        )
    if target_status in REASON_REQUIRED_STATUSES and reason_code is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"reason_code is required when moving a job to {target_status.value}",
        )
    if target_status in STATUS_CHANGE_ASSIGNEE_REQUIRED_STATUSES and not job_has_assignee(job):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"{target_status.value} requires an assignee",
        )


def validate_assignment_fields_for_dispatch_ending_status(
    *,
    changes: dict[str, object],
    target_status: JobStatus | None,
) -> None:
    if target_status not in ASSIGNMENT_ENDING_STATUSES:
        return
    if "assigned_org_id" not in changes and "assigned_contractor_user_id" not in changes:
        return
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=f"{target_status.value} ends the current dispatch; omit assignment fields from the same update",
    )


@router.get("/me", response_model=UserRead)
def api_me(current_user: User = Depends(get_current_user)):
    return serialize_user(current_user)


@router.post("/jobs", response_model=JobRead, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: JobCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    if current_user.organisation_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User must belong to an organisation")

    reporter = current_user
    intake_channel = payload.intake_channel or ReportChannel.resident_portal
    if current_user.role == UserRole.resident:
        if payload.reported_for_user_id is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Residents cannot create jobs on behalf of another user",
            )
        if intake_channel != ReportChannel.resident_portal:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Residents must use intake_channel=resident_portal",
            )
    elif current_user.role in OPERATIONS_ROLES:
        if payload.reported_for_user_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Operations-created jobs require reported_for_user_id",
            )
        reporter = session.get(User, payload.reported_for_user_id)
        if reporter is None or reporter.role != UserRole.resident:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="reported_for_user_id must be a resident",
            )
        if reporter.organisation_id != current_user.organisation_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Resident reporter must belong to the same organisation",
            )
        if intake_channel not in OPERATIONS_INTAKE_CHANNELS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    "Operations intake_channel must be one of staff_created, security_after_hours, "
                    "or inspection_housekeeping"
                ),
            )
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This role cannot create jobs")

    location = session.get(Location, payload.location_id)
    if (
        location is None
        or location.organisation_id != reporter.organisation_id
        or not is_reportable_location(location)
    ):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Choose a valid location")
    if reporter.role == UserRole.resident and not can_user_report_location(session, user=reporter, location=location):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Choose a location within the resident's reportable area",
        )
    asset = None
    if payload.asset_name is not None:
        asset_name = clean_text(payload.asset_name, "asset_name")
        asset = find_asset_by_name(session, location=location, name=asset_name)
        if asset is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Choose a known asset for that location or leave asset_name blank",
            )
    job = Job(
        title=clean_text(payload.title, "title"),
        description=clean_text(payload.description, "description"),
        organisation_id=reporter.organisation_id,
        location_snapshot=location_label(location),
        asset_snapshot=asset.name if asset is not None else None,
        location_detail_text=payload.location_detail_text,
        location_id=location.id,
        asset_id=asset.id if asset is not None else None,
        status=JobStatus.new,
        created_by=current_user.id,
        reported_for_user_id=reporter.id,
        created_by_name_snapshot=current_user.name,
        reported_for_user_name_snapshot=reporter.name,
    )
    session.add(job)
    session.flush()
    append_event(
        session,
        job=job,
        actor=current_user,
        message=report_created_message(
            intake_channel=intake_channel,
            current_user=current_user,
            reporter=reporter,
        ),
        event_type=EventType.report_created,
        target_status=JobStatus.new,
        reason_code=intake_channel.value,
        responsibility_stage=ResponsibilityStage.reception,
    )
    sync_job_status_from_events(job)
    session.commit()
    return serialize_job_for_user(session, current_user, job=visible_job(session, current_user, job.id))


@router.get("/jobs", response_model=list[JobRead])
def list_jobs(
    mine: bool = False,
    assigned: bool = False,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return [
        serialize_job_for_user(session, current_user, job=job)
        for job in visible_jobs(session, current_user, mine=mine, assigned=assigned)
    ]


@router.get("/jobs/{job_id}", response_model=JobRead)
def get_job(
    job_id: uuid.UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return serialize_job_with_history(session, current_user, job=visible_job(session, current_user, job_id))

def build_assignment_events(
    *,
    job: Job,
    previous_scope,
) -> list[EventSpec]:
    events: list[EventSpec] = []
    current_scope = assignee_scope(job)
    current_label = assignee_label(job)

    if current_label is None:
        events.append(
            EventSpec(
                message="Assignment cleared",
                event_type=EventType.assignment,
                responsibility_stage=ResponsibilityStage.coordination,
                owner_scope=previous_scope,
                responsibility_owner=ResponsibilityOwner.coordinator,
                assigned_org_id=None,
                assigned_contractor_user_id=None,
            )
        )
        return events

    message = "Assigned" if previous_scope is None else "Reassigned"
    message = f"{message} {current_label}"
    events.append(
        EventSpec(
            message=message,
            event_type=EventType.assignment,
            responsibility_stage=ResponsibilityStage.coordination,
            owner_scope=current_scope,
            responsibility_owner=ResponsibilityOwner.coordinator,
            assigned_org_id=job.assigned_org_id,
            assigned_contractor_user_id=job.assigned_contractor_user_id,
        )
    )
    return events


def build_assignment_end_event(*, job: Job) -> EventSpec | None:
    if not job_has_assignee(job):
        return None
    return EventSpec(
        message="Assignment cleared",
        event_type=EventType.assignment,
        responsibility_stage=ResponsibilityStage.coordination,
        owner_scope=assignee_scope(job),
        responsibility_owner=ResponsibilityOwner.coordinator,
        assigned_org_id=None,
        assigned_contractor_user_id=None,
    )


def build_contractor_field_ownership_event(
    *,
    job: Job,
    actor: User,
    target_status: JobStatus | None = None,
) -> EventSpec | None:
    if actor.role != UserRole.contractor:
        return None
    if actor.organisation_id is None or actor.organisation_id != job.assigned_org_id:
        return None
    if job.assigned_contractor_user_id == actor.id:
        return None
    if job.assigned_contractor_user_id is not None:
        return None
    effective_status = target_status or job.status
    if effective_status not in CONTRACTOR_FIELD_OWNERSHIP_STATUSES:
        return None

    job.assigned_contractor = actor
    job.assigned_contractor_user_id = actor.id
    if job.assigned_org is None and actor.organisation is not None:
        job.assigned_org = actor.organisation
        job.assigned_org_id = actor.organisation_id

    organisation_name = actor.organisation.name if actor.organisation is not None else "their organisation"
    return EventSpec(
        message=f"{actor.name} took field ownership for {organisation_name}",
        event_type=EventType.assignment,
        responsibility_stage=ResponsibilityStage.execution,
        owner_scope=OwnerScope.user,
        responsibility_owner=ResponsibilityOwner.contractor,
        assigned_org_id=job.assigned_org_id,
        assigned_contractor_user_id=job.assigned_contractor_user_id,
    )


def default_note_accountability(
    reason_code: str | None,
) -> tuple[ResponsibilityStage | None, OwnerScope | None, ResponsibilityOwner | None]:
    if reason_code is None:
        return None, None, None
    return NOTE_REASON_DEFAULTS.get(reason_code, (None, None, None))


def apply_assignment_change(
    *,
    session: Session,
    job: Job,
    actor: User,
    payload: JobUpdate,
    explicit_status_change: bool,
) -> list[EventSpec]:
    changes = payload.model_dump(exclude_unset=True)
    org_field_present = "assigned_org_id" in changes
    user_field_present = "assigned_contractor_user_id" in changes
    if not org_field_present and not user_field_present:
        return []

    if actor.role not in ASSIGNMENT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only coordinators or admins can change assignment",
        )

    requested_org_id = changes.get("assigned_org_id", job.assigned_org_id)
    requested_contractor_user_id = changes.get("assigned_contractor_user_id", job.assigned_contractor_user_id)

    if org_field_present and requested_org_id is not None and not user_field_present:
        requested_contractor_user_id = None

    if job.status == JobStatus.completed and not explicit_status_change:
        if requested_org_id is not None or requested_contractor_user_id is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Completed jobs must be reopened or moved to follow_up_scheduled before reassignment",
            )

    assignment_changed = (
        requested_org_id != job.assigned_org_id or requested_contractor_user_id != job.assigned_contractor_user_id
    )
    if not assignment_changed:
        return []

    validate_assignment_change_requires_explicit_status(job, explicit_status_change=explicit_status_change)
    validate_assignment_clear_requires_explicit_status(
        job,
        explicit_status_change=explicit_status_change,
        will_have_assignee=requested_org_id is not None or requested_contractor_user_id is not None,
    )

    previous_scope = assignee_scope(job)
    organisation = None
    contractor_user = None

    if requested_org_id is not None:
        organisation = session.get(Organisation, requested_org_id)
        if organisation is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation not found")
        if organisation.type != OrganisationType.contractor:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only contractor organisations can be assigned",
            )

    if requested_contractor_user_id is not None:
        contractor_user = session.get(User, requested_contractor_user_id)
        if contractor_user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contractor user not found")
        if contractor_user.role != UserRole.contractor:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only contractor users can be assigned directly",
            )
        contractor_org = contractor_user.organisation
        if contractor_org is None or contractor_org.type != OrganisationType.contractor:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Direct contractors must belong to a contractor organisation",
            )
        if requested_org_id is not None and requested_org_id != contractor_org.id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Direct contractor assignment must use the contractor's organisation",
            )
        requested_org_id = contractor_org.id
        organisation = contractor_org

    if requested_contractor_user_id is None and user_field_present and not org_field_present:
        requested_org_id = job.assigned_org_id
        organisation = job.assigned_org

    if requested_org_id is not None and organisation is None:
        organisation = session.get(Organisation, requested_org_id)

    job.assigned_org = organisation
    job.assigned_contractor = contractor_user
    job.assigned_org_id = requested_org_id
    job.assigned_contractor_user_id = requested_contractor_user_id

    events = build_assignment_events(
        job=job,
        previous_scope=previous_scope,
    )

    requested_status = changes.get("status")
    if requested_status in STATUS_CHANGE_ASSIGNEE_REQUIRED_STATUSES and not job_has_assignee(job):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"{requested_status.value} requires an assignee",
        )

    return events


def merge_assignment_status_event(
    *,
    assignment_events: list[EventSpec],
    status_event: EventSpec | None,
) -> tuple[list[EventSpec], bool]:
    if status_event is None or status_event.target_status != JobStatus.assigned:
        return assignment_events, False

    for index in range(len(assignment_events) - 1, -1, -1):
        candidate = assignment_events[index]
        if candidate.event_type != EventType.assignment:
            continue
        merged_message = candidate.message
        if (
            status_event.message
            and status_event.message != STATUS_EVENT_MESSAGES[JobStatus.assigned]
            and status_event.message != candidate.message
        ):
            merged_message = f"{candidate.message}. {status_event.message}"
        assignment_events[index] = EventSpec(
            message=merged_message,
            event_type=candidate.event_type,
            target_status=status_event.target_status,
            reason_code=status_event.reason_code,
            responsibility_stage=status_event.responsibility_stage,
            owner_scope=status_event.owner_scope,
            responsibility_owner=status_event.responsibility_owner,
            assigned_org_id=candidate.assigned_org_id,
            assigned_contractor_user_id=candidate.assigned_contractor_user_id,
        )
        return assignment_events, True

    return assignment_events, False


@router.patch("/jobs/{job_id}", response_model=JobRead)
def update_job(
    job_id: uuid.UUID,
    payload: JobUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    job = visible_job(session, current_user, job_id)
    sync_job_assignment_from_events(job)
    sync_job_status_from_events(job)
    changes = payload.model_dump(exclude_unset=True)
    explicit_status_change = "status" in changes
    requested_status = changes.get("status")
    transition_event_message = changes.get("event_message")
    transition_reason_code = changes.get("reason_code")
    transition_stage = changes.get("responsibility_stage")
    transition_scope = changes.get("owner_scope")
    transition_owner = changes.get("responsibility_owner")

    if current_user.role == UserRole.resident:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Residents cannot update jobs")
    if current_user.role == UserRole.contractor and not contractor_has_current_assignment(job, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the currently assigned contractor can update this job",
        )

    if not explicit_status_change and any(
        key in changes
        for key in ("event_message", "reason_code", "responsibility_stage", "owner_scope", "responsibility_owner")
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "event_message, reason_code, responsibility_stage, owner_scope, and "
                "responsibility_owner require a status change"
            ),
        )
    validate_assignment_fields_for_dispatch_ending_status(
        changes=changes,
        target_status=requested_status,
    )

    messages = apply_assignment_change(
        session=session,
        job=job,
        actor=current_user,
        payload=payload,
        explicit_status_change=explicit_status_change,
    )
    field_ownership_event = build_contractor_field_ownership_event(
        job=job,
        actor=current_user,
        target_status=requested_status if explicit_status_change else None,
    )
    if field_ownership_event is not None:
        messages.append(field_ownership_event)

    assignment_end_event: EventSpec | None = None
    if (
        explicit_status_change
        and requested_status in ASSIGNMENT_ENDING_STATUSES
    ):
        assignment_end_event = build_assignment_end_event(job=job)
        if assignment_end_event is not None:
            messages.append(assignment_end_event)

    if explicit_status_change:
        validate_transition_request(
            job=job,
            target_status=requested_status,
            event_message=transition_event_message,
            reason_code=transition_reason_code,
        )
        status_event = apply_status_change(
            job,
            requested_status,
            current_user,
            message=transition_event_message,
            reason_code=transition_reason_code,
            responsibility_stage=transition_stage,
            owner_scope=transition_scope,
            responsibility_owner=transition_owner,
        )
        messages, merged_assignment_status = merge_assignment_status_event(
            assignment_events=messages,
            status_event=status_event,
        )
        if status_event is not None and not merged_assignment_status:
            messages.append(status_event)

    for spec in messages:
        append_event(
            session,
            job=job,
            actor=current_user,
            message=spec.message,
            event_type=spec.event_type,
            target_status=spec.target_status,
            reason_code=spec.reason_code,
            responsibility_stage=spec.responsibility_stage,
            owner_scope=spec.owner_scope,
            responsibility_owner=spec.responsibility_owner,
            assigned_org_id=spec.assigned_org_id,
            assigned_contractor_user_id=spec.assigned_contractor_user_id,
        )
    if messages:
        sync_job_assignment_from_events(job)
        sync_job_status_from_events(job)

    session.commit()
    return serialize_job_for_user(session, current_user, job=visible_job(session, current_user, job.id))


@router.get("/jobs/{job_id}/events", response_model=list[EventRead])
def get_job_events(
    job_id: uuid.UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    visible_job(session, current_user, job_id)
    return [serialize_event(event) for event in visible_events(session, job_id)]


@router.post("/jobs/{job_id}/resident-update", response_model=EventRead, status_code=status.HTTP_201_CREATED)
def add_resident_update(
    job_id: uuid.UUID,
    payload: ResidentUpdateCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    job = visible_job(session, current_user, job_id)
    sync_job_assignment_from_events(job)
    sync_job_status_from_events(job)
    if current_user.role != UserRole.resident:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only residents can add resident updates")
    if payload.reason_code is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="reason_code is required",
        )
    validate_resident_update_reason_for_job(job=job, reason_code=payload.reason_code)
    reason_code = payload.reason_code.value
    responsibility_stage = ResponsibilityStage.reception
    responsibility_owner = ResponsibilityOwner.reception_admin
    if reason_code == ResidentUpdateReason.resident_access_update.value:
        responsibility_stage = ResponsibilityStage.coordination
        responsibility_owner = ResponsibilityOwner.coordinator
    elif reason_code == ResidentUpdateReason.resident_confirmed_resolved.value:
        responsibility_stage = ResponsibilityStage.execution
        responsibility_owner = ResponsibilityOwner.resident
    elif reason_code == ResidentUpdateReason.charge_appeal_submitted.value:
        responsibility_stage = ResponsibilityStage.triage
        responsibility_owner = ResponsibilityOwner.triage_officer
    elif reason_code in {
        ResidentUpdateReason.resident_access_issue.value,
        ResidentUpdateReason.issue_still_present.value,
        ResidentUpdateReason.resident_reported_recurrence.value,
    }:
        responsibility_stage = ResponsibilityStage.triage
        responsibility_owner = ResponsibilityOwner.triage_officer
    event = append_event(
        session,
        job=job,
        actor=current_user,
        message=clean_text(payload.message, "message"),
        event_type=EventType.note,
        reason_code=reason_code,
        responsibility_stage=responsibility_stage,
        owner_scope=OwnerScope.user,
        responsibility_owner=responsibility_owner,
    )
    session.commit()
    return serialize_event(event)


@router.post("/jobs/{job_id}/events", response_model=EventRead, status_code=status.HTTP_201_CREATED)
def add_event(
    job_id: uuid.UUID,
    payload: EventCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    job = visible_job(session, current_user, job_id)
    sync_job_assignment_from_events(job)
    sync_job_status_from_events(job)
    if current_user.role == UserRole.resident:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Residents cannot add timeline events")
    if current_user.role == UserRole.contractor and not contractor_has_current_assignment(job, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the currently assigned contractor can update this job",
        )
    provided_fields = payload.model_dump(exclude_unset=True)
    note_event_kwargs = {
        field_name: provided_fields[field_name]
        for field_name in ("reason_code", "responsibility_stage", "owner_scope", "responsibility_owner")
        if field_name in provided_fields
    }
    default_stage, default_scope, default_owner = default_note_accountability(payload.reason_code)
    if "responsibility_stage" not in note_event_kwargs and default_stage is not None:
        note_event_kwargs["responsibility_stage"] = default_stage
    if "owner_scope" not in note_event_kwargs and default_scope is not None:
        note_event_kwargs["owner_scope"] = default_scope
    if "responsibility_owner" not in note_event_kwargs and default_owner is not None:
        note_event_kwargs["responsibility_owner"] = default_owner
    field_ownership_event = build_contractor_field_ownership_event(job=job, actor=current_user)
    if field_ownership_event is not None:
        append_event(
            session,
            job=job,
            actor=current_user,
            message=field_ownership_event.message,
            event_type=field_ownership_event.event_type,
            target_status=field_ownership_event.target_status,
            reason_code=field_ownership_event.reason_code,
            responsibility_stage=field_ownership_event.responsibility_stage,
            owner_scope=field_ownership_event.owner_scope,
            responsibility_owner=field_ownership_event.responsibility_owner,
            assigned_org_id=field_ownership_event.assigned_org_id,
            assigned_contractor_user_id=field_ownership_event.assigned_contractor_user_id,
        )
    event = append_event(
        session,
        job=job,
        actor=current_user,
        message=clean_text(payload.message, "message"),
        event_type=EventType.note,
        **note_event_kwargs,
    )
    session.commit()
    return serialize_event(event)
