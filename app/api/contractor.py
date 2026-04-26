from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.api.deps import (
    build_focus_counts,
    contractor_has_current_assignment,
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
from app.models import JobStatus, User, UserRole
from app.services import available_status_actions, derive_coordination_projection


router = APIRouter(prefix="/contractor")


@router.get("/jobs", response_class=HTMLResponse, include_in_schema=False)
def contractor_jobs_page(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, UserRole.contractor)
    jobs = sort_jobs_for_queue(
        [
            serialize_job_for_user(session, current_user, job=job)
            for job in visible_jobs(session, current_user, assigned=True)
        ]
    )
    return render_page(
        request=request,
        session=session,
        current_user=current_user,
        template_name="contractor_jobs.html",
        jobs=jobs,
        focus_counts=build_focus_counts(jobs, user=current_user),
    )


@router.get("/jobs/{job_id}", response_class=HTMLResponse, include_in_schema=False)
def contractor_job_page(
    job_id: uuid.UUID,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, UserRole.contractor)
    job = visible_job(session, current_user, job_id)
    events = visible_events(session, job_id)
    can_update_job = contractor_has_current_assignment(job, current_user)
    serialized_job = serialize_job_with_history(session, current_user, job=job)
    status_actions = available_status_actions(
        current_status=JobStatus(serialized_job["status"]),
        actor=current_user,
        has_assignee=serialized_job["assignee_label"] is not None,
        has_current_assignment=can_update_job,
    )
    return render_page(
        request=request,
        session=session,
        current_user=current_user,
        template_name="contractor_job.html",
        job=serialized_job,
        events=[serialize_event(event) for event in events],
        coordination=derive_coordination_projection(job, events),
        can_update_job=can_update_job,
        status_actions=[
            {
                "status": action.status.value,
                "label": action.label,
                "requires_message": action.requires_message,
                "requires_reason": action.requires_reason,
            }
            for action in status_actions
        ],
        related_jobs=related_jobs_for_user(session, current_user, job=job),
    )
