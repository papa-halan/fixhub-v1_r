from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.api.deps import (
    OPERATIONS_ROLES,
    build_focus_counts,
    build_job_counts,
    get_current_user,
    get_session,
    list_contractor_organisations,
    list_contractor_users,
    list_resident_users,
    related_jobs_for_user,
    render_page,
    require_role,
    serialize_event,
    serialize_job_for_user,
    serialize_job_with_history,
    visible_events,
    visible_job,
    visible_jobs,
)
from app.models import JobStatus, ReportChannel, User
from app.services import ASSIGNMENT_ROLES, available_status_actions, build_location_asset_catalog, derive_coordination_projection


router = APIRouter(prefix="/admin")


@router.get("/report", response_class=HTMLResponse, include_in_schema=False)
def admin_report_page(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, *OPERATIONS_ROLES)
    return render_page(
        request=request,
        session=session,
        current_user=current_user,
        template_name="admin_report.html",
        resident_users=list_resident_users(
            session,
            organisation_id=current_user.organisation_id,
            include_demo=request.app.state.settings.demo_mode,
        ),
        location_catalog=build_location_asset_catalog(session, user=current_user),
        intake_channels=[
            {"value": ReportChannel.staff_created.value, "label": "Staff-created"},
            {"value": ReportChannel.security_after_hours.value, "label": "After-hours support"},
            {"value": ReportChannel.inspection_housekeeping.value, "label": "Inspection or housekeeping"},
        ],
    )


@router.get("/jobs", response_class=HTMLResponse, include_in_schema=False)
def admin_jobs_page(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, *OPERATIONS_ROLES)
    jobs = [serialize_job_for_user(session, current_user, job=job) for job in visible_jobs(session, current_user)]
    return render_page(
        request=request,
        session=session,
        current_user=current_user,
        template_name="admin_jobs.html",
        jobs=jobs,
        counts=build_job_counts(jobs),
        focus_counts=build_focus_counts(jobs),
    )


@router.get("/jobs/{job_id}", response_class=HTMLResponse, include_in_schema=False)
def admin_job_page(
    job_id: uuid.UUID,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, *OPERATIONS_ROLES)
    job = visible_job(session, current_user, job_id)
    events = visible_events(session, job_id)
    serialized_job = serialize_job_with_history(session, current_user, job=job)
    status_actions = available_status_actions(
        current_status=JobStatus(serialized_job["status"]),
        actor=current_user,
        has_assignee=serialized_job["assignee_label"] is not None,
    )
    return render_page(
        request=request,
        session=session,
        current_user=current_user,
        template_name="admin_job.html",
        job=serialized_job,
        events=[serialize_event(event) for event in events],
        coordination=derive_coordination_projection(job, events),
        related_jobs=related_jobs_for_user(session, current_user, job=job),
        contractor_orgs=list_contractor_organisations(session),
        contractor_users=list_contractor_users(session, include_demo=request.app.state.settings.demo_mode),
        status_actions=[
            {
                "status": action.status.value,
                "label": action.label,
                "requires_message": action.requires_message,
                "requires_reason": action.requires_reason,
            }
            for action in status_actions
        ],
        can_change_assignment=current_user.role in ASSIGNMENT_ROLES,
    )
