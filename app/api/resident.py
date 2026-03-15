from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_user,
    get_session,
    render_page,
    require_role,
    serialize_event,
    serialize_job,
    visible_events,
    visible_job,
    visible_jobs,
)
from app.models import User, UserRole


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
    )


@router.get("/jobs", response_class=HTMLResponse, include_in_schema=False)
def resident_jobs_page(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, UserRole.resident)
    jobs = [serialize_job(job) for job in visible_jobs(session, current_user, mine=True)]
    return render_page(
        request=request,
        session=session,
        current_user=current_user,
        template_name="resident_jobs.html",
        jobs=jobs,
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
    return render_page(
        request=request,
        session=session,
        current_user=current_user,
        template_name="resident_job.html",
        job=serialize_job(job),
        events=[serialize_event(event) for event in visible_events(session, job_id)],
    )
