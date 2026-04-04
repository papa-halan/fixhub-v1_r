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
    serialize_job,
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
    ResidentUpdateReason,
    ResponsibilityOwner,
    ResponsibilityStage,
    User,
    UserRole,
)
from app.schema import EventCreate, EventRead, JobCreate, JobRead, JobUpdate, ResidentUpdateCreate, UserRead
from app.services.catalog import is_reportable_location, location_label
from app.services import (
    ASSIGNEE_REQUIRED_STATUSES,
    ASSIGNMENT_ROLES,
    EventSpec,
    append_event,
    apply_status_change,
    assignee_label,
    assignee_scope,
    find_asset_by_name,
    job_has_assignee,
    sync_job_assignment_from_events,
    sync_job_status_from_events,
    validate_assignment_clear_requires_explicit_status,
    validate_assignment_change_requires_explicit_status,
)


router = APIRouter(prefix="/api")


@router.get("/me", response_model=UserRead)
def api_me(current_user: User = Depends(get_current_user)):
    return serialize_user(current_user)


@router.post("/jobs", response_model=JobRead, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: JobCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.resident:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only residents can create jobs")
    if current_user.organisation_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User must belong to an organisation")
    location = session.get(Location, payload.location_id)
    if (
        location is None
        or location.organisation_id != current_user.organisation_id
        or not is_reportable_location(location)
    ):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Choose a valid location")
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
        organisation_id=current_user.organisation_id,
        location_snapshot=location_label(location),
        location_detail_text=payload.location_detail_text,
        location_id=location.id,
        asset_id=asset.id if asset is not None else None,
        status=JobStatus.new,
        created_by=current_user.id,
    )
    session.add(job)
    session.flush()
    append_event(
        session,
        job=job,
        actor=current_user,
        message="Report created",
        event_type=EventType.report_created,
        target_status=JobStatus.new,
        responsibility_stage=ResponsibilityStage.reception,
    )
    sync_job_status_from_events(job)
    session.commit()
    return serialize_job(visible_job(session, current_user, job.id))


@router.get("/jobs", response_model=list[JobRead])
def list_jobs(
    mine: bool = False,
    assigned: bool = False,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return [serialize_job(job) for job in visible_jobs(session, current_user, mine=mine, assigned=assigned)]


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
                responsibility_stage=ResponsibilityStage.triage,
                owner_scope=previous_scope,
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
            responsibility_stage=ResponsibilityStage.triage,
            owner_scope=current_scope,
            assigned_org_id=job.assigned_org_id,
            assigned_contractor_user_id=job.assigned_contractor_user_id,
        )
    )
    return events


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
    if requested_status in ASSIGNEE_REQUIRED_STATUSES and not job_has_assignee(job):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"{requested_status.value} requires an assignee",
        )

    return events


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

    messages = apply_assignment_change(
        session=session,
        job=job,
        actor=current_user,
        payload=payload,
        explicit_status_change=explicit_status_change,
    )

    if explicit_status_change:
        status_event = apply_status_change(
            job,
            changes["status"],
            current_user,
            message=transition_event_message,
            reason_code=transition_reason_code,
            responsibility_stage=transition_stage,
            owner_scope=transition_scope,
            responsibility_owner=transition_owner,
        )
        if status_event is not None:
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
        sync_job_status_from_events(job)

    session.commit()
    return serialize_job(visible_job(session, current_user, job.id))


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
    if current_user.role != UserRole.resident:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only residents can add resident updates")
    reason_code = payload.reason_code.value if payload.reason_code is not None else None
    responsibility_stage = ResponsibilityStage.reception
    responsibility_owner = ResponsibilityOwner.reception_admin
    if reason_code == ResidentUpdateReason.resident_access_update.value:
        responsibility_stage = ResponsibilityStage.coordination
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
    if current_user.role == UserRole.resident:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Residents cannot add timeline events")
    if current_user.role == UserRole.contractor and not contractor_has_current_assignment(job, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the currently assigned contractor can update this job",
        )
    event = append_event(
        session,
        job=job,
        actor=current_user,
        message=clean_text(payload.message, "message"),
        event_type=EventType.note,
        reason_code=payload.reason_code,
        responsibility_stage=payload.responsibility_stage,
        owner_scope=payload.owner_scope,
        responsibility_owner=payload.responsibility_owner,
    )
    session.commit()
    return serialize_event(event)
