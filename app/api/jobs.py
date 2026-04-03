from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import (
    clean_text,
    get_current_user,
    get_session,
    serialize_event,
    serialize_job,
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
    ResponsibilityStage,
    User,
    UserRole,
)
from app.schema import EventCreate, EventRead, JobCreate, JobRead, JobUpdate, UserRead
from app.services.catalog import is_reportable_location
from app.services import (
    ASSIGNEE_REQUIRED_STATUSES,
    ASSIGNMENT_ROLES,
    COORDINATION_ROLES,
    EventSpec,
    STATUS_EVENT_MESSAGES,
    TRIAGE_ROLES,
    append_event,
    apply_status_change,
    assignee_label,
    assignee_scope,
    fallback_status_for_unassigned,
    find_or_create_asset,
    job_has_assignee,
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
    asset_name = clean_text(payload.asset_name or payload.title, "asset_name")
    asset = find_or_create_asset(session, location=location, name=asset_name)
    job = Job(
        title=clean_text(payload.title, "title"),
        description=clean_text(payload.description, "description"),
        organisation_id=current_user.organisation_id,
        location_snapshot=location.name,
        location_detail_text=payload.location_detail_text,
        location_id=location.id,
        asset_id=asset.id,
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
    return serialize_job(visible_job(session, current_user, job_id))

def build_assignment_events(
    *,
    job: Job,
    previous_label: str | None,
    previous_scope,
    explicit_status_change: bool,
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
            )
        )
        if not explicit_status_change:
            fallback_status = fallback_status_for_unassigned(job)
            if job.status != fallback_status:
                job.status = fallback_status
                events.append(
                    EventSpec(
                        message=STATUS_EVENT_MESSAGES[fallback_status],
                        event_type=EventType.status_change,
                        target_status=fallback_status,
                        responsibility_stage=ResponsibilityStage.triage
                        if fallback_status == JobStatus.triaged
                        else ResponsibilityStage.reception,
                    )
                )
        return events

    message = f"{'Reassigned' if previous_label else 'Assigned'} {current_label}"
    events.append(
        EventSpec(
            message=message,
            event_type=EventType.assignment,
            responsibility_stage=ResponsibilityStage.triage,
            owner_scope=current_scope,
        )
    )
    if not explicit_status_change and job.status == JobStatus.new:
        job.status = JobStatus.assigned
        events.append(
            EventSpec(
                message=STATUS_EVENT_MESSAGES[JobStatus.assigned],
                event_type=EventType.status_change,
                target_status=JobStatus.assigned,
                responsibility_stage=ResponsibilityStage.triage,
                owner_scope=current_scope,
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
    if user_field_present and requested_contractor_user_id is not None and not org_field_present:
        requested_org_id = None
    if requested_org_id is not None and requested_contractor_user_id is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="assigned_org_id and assigned_contractor_user_id are mutually exclusive",
        )

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

    previous_scope = assignee_scope(job)
    previous_label = assignee_label(job)
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

    job.assigned_org = organisation
    job.assigned_contractor = contractor_user
    job.assigned_org_id = requested_org_id
    job.assigned_contractor_user_id = requested_contractor_user_id

    events = build_assignment_events(
        job=job,
        previous_label=previous_label,
        previous_scope=previous_scope,
        explicit_status_change=explicit_status_change,
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
    changes = payload.model_dump(exclude_unset=True)
    explicit_status_change = "status" in changes
    transition_reason_code = changes.get("reason_code")
    transition_stage = changes.get("responsibility_stage")
    transition_scope = changes.get("owner_scope")

    if current_user.role == UserRole.resident:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Residents cannot update jobs")

    if not explicit_status_change and any(
        key in changes for key in ("reason_code", "responsibility_stage", "owner_scope")
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="reason_code, responsibility_stage, and owner_scope require a status change",
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
            reason_code=transition_reason_code,
            responsibility_stage=transition_stage,
            owner_scope=transition_scope,
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
        )

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
    event = append_event(
        session,
        job=job,
        actor=current_user,
        message=clean_text(payload.message, "message"),
        event_type=EventType.note,
    )
    session.commit()
    return serialize_event(event)
