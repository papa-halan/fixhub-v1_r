from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import (
    append_event,
    apply_status_change,
    clean_text,
    get_current_user,
    get_session,
    require_role,
    serialize_event,
    serialize_job,
    serialize_user,
    visible_events,
    visible_job,
    visible_jobs,
)
from app.models import Job, JobStatus, Organisation, OrganisationType, User, UserRole
from app.schema import EventCreate, EventRead, JobCreate, JobRead, JobUpdate, UserRead
from app.services import find_or_create_asset, find_or_create_location


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
    require_role(current_user, UserRole.resident)
    location_name = clean_text(payload.location, "location")
    location = find_or_create_location(session, user=current_user, name=location_name)
    asset_name = clean_text(payload.asset_name or payload.title, "asset_name")
    asset = find_or_create_asset(session, location=location, name=asset_name)
    job = Job(
        title=clean_text(payload.title, "title"),
        description=clean_text(payload.description, "description"),
        location=location_name,
        location_id=location.id,
        asset_id=asset.id,
        status=JobStatus.new,
        created_by=current_user.id,
    )
    session.add(job)
    session.flush()
    append_event(session, job=job, actor=current_user, message="Report created")
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


@router.patch("/jobs/{job_id}", response_model=JobRead)
def update_job(
    job_id: uuid.UUID,
    payload: JobUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    job = visible_job(session, current_user, job_id)
    changes = payload.model_dump(exclude_unset=True)

    if current_user.role == UserRole.resident:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Residents cannot update jobs")

    messages: list[str] = []

    if "assigned_org_id" in changes:
        if current_user.role != UserRole.admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can assign contractors")

        requested_org_id = changes["assigned_org_id"]
        if requested_org_id is None:
            if job.assigned_org_id is not None:
                job.assigned_org_id = None
                messages.append("Assignment cleared")
                if job.status == JobStatus.assigned and "status" not in changes:
                    job.status = JobStatus.new
                    messages.append("Moved job back to new")
        elif requested_org_id != job.assigned_org_id:
            organisation = session.get(Organisation, requested_org_id)
            if organisation is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation not found")
            if organisation.type != OrganisationType.contractor:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only contractor organisations can be assigned")
            was_assigned = job.assigned_org_id is not None
            job.assigned_org = organisation
            messages.append(f"{'Reassigned' if was_assigned else 'Assigned'} {organisation.name}")
            if job.status == JobStatus.new and "status" not in changes:
                job.status = JobStatus.assigned
                messages.append("Marked job assigned")

    if "status" in changes:
        status_message = apply_status_change(job, changes["status"], current_user)
        if status_message is not None:
            messages.append(status_message)

    for message in messages:
        append_event(session, job=job, actor=current_user, message=message)

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
    event = append_event(
        session,
        job=job,
        actor=current_user,
        message=clean_text(payload.message, "message"),
    )
    session.commit()
    return serialize_event(event)
