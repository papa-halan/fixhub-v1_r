from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.api.deps import (
    build_focus_counts,
    get_current_user,
    get_session,
    related_jobs_for_user,
    render_page,
    require_role,
    serialize_event,
    serialize_job_for_user,
    serialize_job_with_history,
    sort_jobs_for_queue,
    visible_events,
    visible_job,
    visible_jobs,
)
from app.models import User, UserRole
from app.services import build_location_asset_catalog, derive_coordination_projection


router = APIRouter(prefix="/resident")


@router.get("/report", response_class=HTMLResponse, include_in_schema=False)
def resident_report_page(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, UserRole.resident)
    return render_page(
        request=request,
        session=session,
        current_user=current_user,
        template_name="resident_report.html",
        location_catalog=build_location_asset_catalog(session, user=current_user),
    )


@router.get("/jobs", response_class=HTMLResponse, include_in_schema=False)
def resident_jobs_page(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, UserRole.resident)
    jobs = sort_jobs_for_queue(
        [serialize_job_for_user(session, current_user, job=job) for job in visible_jobs(session, current_user, mine=True)]
    )
    return render_page(
        request=request,
        session=session,
        current_user=current_user,
        template_name="resident_jobs.html",
        jobs=jobs,
        focus_counts=build_focus_counts(jobs),
    )


@router.get("/jobs/{job_id}", response_class=HTMLResponse, include_in_schema=False)
def resident_job_page(
    job_id: uuid.UUID,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, UserRole.resident)
    job = visible_job(session, current_user, job_id)
    events = visible_events(session, job_id)
    return render_page(
        request=request,
        session=session,
        current_user=current_user,
        template_name="resident_job.html",
        job=serialize_job_with_history(session, current_user, job=job),
        events=[serialize_event(event) for event in events],
        coordination=derive_coordination_projection(job, events),
        related_jobs=related_jobs_for_user(session, current_user, job=job),
    )
