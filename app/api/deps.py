from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.security import verify_session_token
from app.models import (
    Event,
    Job,
    JobStatus,
    Organisation,
    OrganisationType,
    ReportChannel,
    User,
    UserRole,
)
from app.services import (
    OPERATIONS_ROLES,
    derive_activity_gap,
    derive_assignment_projection,
    derive_coordination_projection,
    derive_pending_signal,
    derive_visit_plan,
    latest_role_update,
    list_demo_users,
    role_label,
    location_label,
)
from app.services import status_label, user_role_label


APP_DIR = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))


def format_timestamp(value: datetime) -> str:
    return value.astimezone().strftime("%d %b %H:%M")


templates.env.filters["timestamp"] = format_timestamp


ROLE_HOMES = {
    UserRole.resident: "/resident/report",
    UserRole.admin: "/admin/jobs",
    UserRole.reception_admin: "/admin/jobs",
    UserRole.triage_officer: "/admin/jobs",
    UserRole.coordinator: "/admin/jobs",
    UserRole.contractor: "/contractor/jobs",
}

RESOLVED_JOB_STATUSES = {JobStatus.completed, JobStatus.cancelled}


@dataclass(frozen=True)
class OperationalHistoryProjection:
    headline: str
    summary: str
    location_job_count: int
    asset_job_count: int
    open_job_count: int


@dataclass(frozen=True)
class QueuePriorityProjection:
    label: str
    summary: str
    rank: int


@dataclass(frozen=True)
class ReportIntakeProjection:
    channel: str | None
    channel_label: str | None
    summary: str | None
    actor_label: str | None


REPORT_CHANNEL_LABELS = {
    ReportChannel.resident_portal.value: "Resident portal",
    ReportChannel.staff_created.value: "Staff-created",
    ReportChannel.security_after_hours.value: "After-hours support",
    ReportChannel.inspection_housekeeping.value: "Inspection or housekeeping",
}

BLOCKED_QUEUE_PRIORITY_RANK = 0
RESPONSE_NEEDED_QUEUE_PRIORITY_RANK = 1
VISIT_ATTENTION_QUEUE_PRIORITY_RANK = 2
REPEAT_OPEN_QUEUE_PRIORITY_RANK = 3
STATE_GAP_QUEUE_PRIORITY_RANK = 4
RECENT_ACTIVITY_QUEUE_PRIORITY_RANK = 5


def get_session(request: Request):
    session = request.app.state.SessionLocal()
    try:
        yield session
    finally:
        session.close()


def clean_text(value: str, field_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise HTTPException(status_code=422, detail=f"{field_name} cannot be blank")
    return cleaned


def user_query():
    return select(User).options(joinedload(User.organisation))


def job_query():
    return (
        select(Job)
        .options(
            joinedload(Job.creator).joinedload(User.organisation),
            joinedload(Job.reported_for_user).joinedload(User.organisation),
            joinedload(Job.organisation),
            joinedload(Job.location),
            joinedload(Job.asset),
            joinedload(Job.assigned_org),
            joinedload(Job.assigned_contractor).joinedload(User.organisation),
            selectinload(Job.events).options(
                joinedload(Event.assigned_org),
                joinedload(Event.assigned_contractor).joinedload(User.organisation),
            ),
        )
        .order_by(Job.updated_at.desc(), Job.created_at.desc())
    )


def event_query(job_id: uuid.UUID):
    return (
        select(Event)
        .where(Event.job_id == job_id)
        .options(
            joinedload(Event.job).joinedload(Job.organisation),
            joinedload(Event.job).joinedload(Job.location),
            joinedload(Event.job).joinedload(Job.asset),
            joinedload(Event.job).joinedload(Job.assigned_org),
            joinedload(Event.job).joinedload(Job.assigned_contractor).joinedload(User.organisation),
            joinedload(Event.actor_user).joinedload(User.organisation),
            joinedload(Event.actor_org),
            joinedload(Event.assigned_org),
            joinedload(Event.assigned_contractor).joinedload(User.organisation),
            joinedload(Event.location_record),
            joinedload(Event.asset),
        )
        .order_by(Event.created_at.asc(), Event.id.asc())
    )


def lookup_current_user(
    request: Request,
    session: Session,
) -> tuple[bool, User | None]:
    if hasattr(request.state, "current_user") and hasattr(request.state, "invalid_session"):
        cached_user = request.state.current_user
        if cached_user is None:
            return bool(request.state.invalid_session), None
        bound_user = session.scalar(user_query().where(User.id == cached_user.id).limit(1))
        if bound_user is None:
            return True, None
        request.state.current_user = bound_user
        return bool(request.state.invalid_session), bound_user

    settings = request.app.state.settings
    token = (request.cookies.get(settings.session_cookie_name) or "").strip()
    if not token:
        return False, None

    user_id = verify_session_token(token, secret=settings.session_secret)
    if user_id is None:
        return True, None

    user = session.scalar(user_query().where(User.id == user_id).limit(1))
    if user is None:
        return True, None
    return False, user


def get_current_user(
    request: Request,
    session: Session = Depends(get_session),
) -> User:
    _invalid_cookie, user = lookup_current_user(request, session)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return user


def require_role(user: User, *roles: UserRole) -> None:
    if user.role not in roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot access this page")


def home_path_for(role: UserRole) -> str:
    return ROLE_HOMES[role]


def navigation_for(user: User) -> list[dict[str, str]]:
    if user.role == UserRole.resident:
        return [
            {"label": "Report Issue", "href": "/resident/report"},
            {"label": "My Reports", "href": "/resident/jobs"},
        ]
    if user.role in OPERATIONS_ROLES:
        return [
            {"label": "Operations Queue", "href": "/admin/jobs"},
            {"label": "Log Intake", "href": "/admin/report"},
        ]
    return [{"label": "Assigned Work", "href": "/contractor/jobs"}]


def actor_name(event: Event) -> str:
    if event.actor_name_snapshot:
        return event.actor_name_snapshot
    if event.actor_user:
        return event.actor_user.name
    if event.actor_org:
        return event.actor_org.name
    return "System"


def actor_role_value(event: Event) -> str | None:
    if event.actor_role_snapshot:
        return event.actor_role_snapshot
    if event.actor_user:
        return event.actor_user.role.value
    return None


def actor_role_label(event: Event) -> str | None:
    if event.actor_role_snapshot:
        return role_label(event.actor_role_snapshot)
    if event.actor_user:
        return user_role_label(event.actor_user)
    return role_label(actor_role_value(event))


def organisation_name(event: Event) -> str | None:
    if event.actor_org_name_snapshot:
        return event.actor_org_name_snapshot
    if event.actor_user and event.actor_user.organisation:
        return event.actor_user.organisation.name
    if event.actor_org:
        return event.actor_org.name
    return None


def actor_label(event: Event) -> str:
    name = actor_name(event)
    role = actor_role_label(event)
    organisation = organisation_name(event)
    if role and organisation:
        return f"{name} ({role}, {organisation})"
    if role:
        return f"{name} ({role})"
    if organisation:
        return f"{name} ({organisation})"
    return name


def serialize_user(user: User) -> dict[str, object]:
    organisation = user.organisation
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role.value,
        "role_label": user_role_label(user),
        "organisation_id": organisation.id if organisation else None,
        "organisation_name": organisation.name if organisation else None,
        "organisation_type": organisation.type.value if organisation else None,
        "created_at": user.created_at,
    }


def job_location_name(job: Job) -> str:
    if job.location_snapshot:
        return job.location_snapshot
    assert job.location is not None
    return location_label(job.location)


def job_asset_name(job: Job) -> str | None:
    if job.asset_snapshot:
        return job.asset_snapshot
    if job.asset:
        return job.asset.name
    return None


def job_reported_for_name(job: Job) -> str:
    reported_for_user = getattr(job, "reported_for_user", None)
    if reported_for_user is not None:
        return reported_for_user.name
    creator = getattr(job, "creator", None)
    if creator is not None:
        return creator.name
    return "Resident"


def serialize_job(job: Job) -> dict[str, object]:
    intake = derive_report_intake(job)
    assignment = derive_assignment_projection(job, job.events)
    projection = derive_coordination_projection(job, job.events)
    pending_signal = derive_pending_signal(job, job.events)
    visit_plan = derive_visit_plan(job, job.events)
    activity_gap = derive_activity_gap(job, job.events)
    latest_event = max(job.events, key=lambda event: (event.created_at, event.id)) if job.events else None
    lifecycle_event = (
        next((event for event in job.events if event.id == projection.latest_lifecycle_event_id), None)
        if projection.latest_lifecycle_event_id is not None
        else None
    )
    latest_resident_update = latest_role_update(job.events, roles={UserRole.resident.value})
    latest_operations_update = latest_role_update(
        job.events,
        roles={
            UserRole.admin.value,
            UserRole.reception_admin.value,
            UserRole.triage_officer.value,
            UserRole.coordinator.value,
        },
    )
    latest_contractor_update = latest_role_update(job.events, roles={UserRole.contractor.value})
    return {
        "id": job.id,
        "title": job.title,
        "description": job.description,
        "organisation_id": job.organisation_id,
        "location": job_location_name(job),
        "location_id": job.location_id,
        "location_detail_text": job.location_detail_text,
        "asset_id": job.asset_id,
        "asset_name": job_asset_name(job),
        "status": projection.status.value,
        "status_label": status_label(projection.status),
        "coordination_headline": projection.headline,
        "coordination_owner_label": projection.owner_label,
        "coordination_detail": projection.detail,
        "action_required_by": projection.action_required_by,
        "action_required_summary": projection.action_required_summary,
        "responsibility_stage": projection.responsibility_stage,
        "owner_scope": projection.owner_scope,
        "created_by": job.created_by,
        "created_by_name": job.creator.name,
        "reported_for_user_id": job.reported_for_user_id,
        "reported_for_user_name": job_reported_for_name(job),
        "intake_channel": intake.channel,
        "intake_channel_label": intake.channel_label,
        "intake_summary": intake.summary,
        "reported_by_actor_label": intake.actor_label,
        "responsibility_owner": projection.responsibility_owner,
        "assigned_org_id": assignment.assigned_org_id,
        "assigned_org_name": assignment.assigned_org_name,
        "assigned_contractor_user_id": assignment.assigned_contractor_user_id,
        "assigned_contractor_name": assignment.assigned_contractor_name,
        "assignee_scope": assignment.assignee_scope,
        "assignee_label": assignment.assignee_label,
        "latest_event_type": projection.latest_event_type,
        "latest_event_actor_label": actor_label(latest_event) if latest_event is not None else None,
        "latest_event_at": projection.latest_event_at,
        "latest_lifecycle_event_type": projection.latest_lifecycle_event_type,
        "latest_lifecycle_event_actor_label": actor_label(lifecycle_event) if lifecycle_event is not None else None,
        "latest_lifecycle_event_at": projection.latest_lifecycle_event_at,
        "latest_resident_update_message": (
            latest_resident_update.message if latest_resident_update is not None else None
        ),
        "latest_resident_update_actor_label": (
            latest_resident_update.actor_label if latest_resident_update is not None else None
        ),
        "latest_resident_update_at": latest_resident_update.created_at if latest_resident_update is not None else None,
        "latest_operations_update_message": (
            latest_operations_update.message if latest_operations_update is not None else None
        ),
        "latest_operations_update_actor_label": (
            latest_operations_update.actor_label if latest_operations_update is not None else None
        ),
        "latest_operations_update_at": (
            latest_operations_update.created_at if latest_operations_update is not None else None
        ),
        "latest_contractor_update_message": (
            latest_contractor_update.message if latest_contractor_update is not None else None
        ),
        "latest_contractor_update_actor_label": (
            latest_contractor_update.actor_label if latest_contractor_update is not None else None
        ),
        "latest_contractor_update_at": (
            latest_contractor_update.created_at if latest_contractor_update is not None else None
        ),
        "pending_signal_headline": pending_signal.headline if pending_signal is not None else None,
        "pending_signal_summary": pending_signal.summary if pending_signal is not None else None,
        "pending_signal_actor_label": pending_signal.actor_label if pending_signal is not None else None,
        "pending_signal_at": pending_signal.created_at if pending_signal is not None else None,
        "activity_gap_headline": activity_gap.headline if activity_gap is not None else None,
        "activity_gap_summary": activity_gap.summary if activity_gap is not None else None,
        "activity_gap_at": activity_gap.latest_event_at if activity_gap is not None else None,
        "visit_plan_headline": visit_plan.headline if visit_plan is not None else None,
        "visit_plan_summary": visit_plan.summary if visit_plan is not None else None,
        "visit_dispatch_message": visit_plan.dispatch_message if visit_plan is not None else None,
        "visit_dispatch_actor_label": visit_plan.dispatch_actor_label if visit_plan is not None else None,
        "visit_dispatch_at": visit_plan.dispatch_at if visit_plan is not None else None,
        "visit_booking_message": visit_plan.booking_message if visit_plan is not None else None,
        "visit_booking_actor_label": visit_plan.booking_actor_label if visit_plan is not None else None,
        "visit_booking_at": visit_plan.booking_at if visit_plan is not None else None,
        "visit_access_message": visit_plan.access_message if visit_plan is not None else None,
        "visit_access_actor_label": visit_plan.access_actor_label if visit_plan is not None else None,
        "visit_access_at": visit_plan.access_at if visit_plan is not None else None,
        "visit_blocker_message": visit_plan.blocker_message if visit_plan is not None else None,
        "visit_blocker_actor_label": visit_plan.blocker_actor_label if visit_plan is not None else None,
        "visit_blocker_at": visit_plan.blocker_at if visit_plan is not None else None,
        "operational_history_headline": None,
        "operational_history_summary": None,
        "operational_history_location_job_count": 0,
        "operational_history_asset_job_count": 0,
        "operational_history_open_job_count": 0,
        "queue_priority_label": None,
        "queue_priority_summary": None,
        "queue_priority_rank": RECENT_ACTIVITY_QUEUE_PRIORITY_RANK,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


def serialize_job_for_user(
    session: Session,
    user: User,
    *,
    job: Job,
    include_history: bool = True,
) -> dict[str, object]:
    payload = serialize_job(job)
    if not include_history:
        return payload

    history = operational_history_for_user(session, user, job=job)
    payload.update(
        {
            "operational_history_headline": history.headline,
            "operational_history_summary": history.summary,
            "operational_history_location_job_count": history.location_job_count,
            "operational_history_asset_job_count": history.asset_job_count,
            "operational_history_open_job_count": history.open_job_count,
        }
    )
    queue_priority = derive_queue_priority(payload)
    payload.update(
        {
            "queue_priority_label": queue_priority.label,
            "queue_priority_summary": queue_priority.summary,
            "queue_priority_rank": queue_priority.rank,
        }
    )
    return payload


def event_location_name(event: Event) -> str | None:
    if event.location_snapshot:
        return event.location_snapshot
    if event.location_record:
        if event.job and event.job.location_snapshot:
            return event.job.location_snapshot
        return location_label(event.location_record)
    if event.job:
        return job_location_name(event.job)
    return None


def event_asset_name(event: Event) -> str | None:
    if event.asset_snapshot:
        return event.asset_snapshot
    if event.asset:
        return event.asset.name
    if event.job:
        return job_asset_name(event.job)
    return None


def serialize_event(event: Event) -> dict[str, object]:
    role = actor_role_value(event)
    return {
        "id": event.id,
        "job_id": event.job_id,
        "location_id": event.location_id or (event.job.location_id if event.job else None),
        "location": event_location_name(event),
        "asset_id": event.asset_id or (event.job.asset_id if event.job else None),
        "asset_name": event_asset_name(event),
        "actor_user_id": event.actor_user_id,
        "actor_org_id": event.actor_org_id,
        "actor_name": actor_name(event),
        "actor_role": role,
        "actor_role_label": actor_role_label(event),
        "organisation_name": organisation_name(event),
        "assigned_org_id": event.assigned_org_id,
        "assigned_org_name": event.assigned_org_name_snapshot
        or (event.assigned_org.name if event.assigned_org else None),
        "assigned_contractor_user_id": event.assigned_contractor_user_id,
        "assigned_contractor_name": event.assigned_contractor_name_snapshot
        or (event.assigned_contractor.name if event.assigned_contractor else None),
        "actor_label": actor_label(event),
        "event_type": event.event_type.value,
        "target_status": event.target_status.value if event.target_status else None,
        "message": event.message,
        "reason_code": event.reason_code,
        "responsibility_stage": event.responsibility_stage.value if event.responsibility_stage else None,
        "owner_scope": event.owner_scope.value if event.owner_scope else None,
        "responsibility_owner": event.responsibility_owner.value if event.responsibility_owner else None,
        "created_at": event.created_at,
    }


def serialize_demo_user(user: User) -> dict[str, str]:
    return {
        "email": user.email,
        "label": user.name,
        "role": user.role.value,
        "role_label": user_role_label(user),
        "home_path": home_path_for(user.role),
    }


def build_job_counts(jobs: list[dict[str, object]]) -> dict[str, int]:
    counts = {status.value: 0 for status in JobStatus}
    counts["total"] = len(jobs)
    for job in jobs:
        counts[str(job["status"])] += 1
    return counts


VISIT_PLAN_ATTENTION_HEADLINES = {
    "Attendance planning not recorded yet",
    "Attendance still needs a booked visit",
    "Access arrangement is not ready for the next visit",
    "Resident access note is newer than the booked visit",
}


def build_focus_counts(jobs: list[dict[str, object]]) -> dict[str, int]:
    return {
        "response_needed": len([job for job in jobs if job.get("pending_signal_at") is not None]),
        "state_gap": len([job for job in jobs if job.get("activity_gap_at") is not None]),
        "visit_attention": len(
            [
                job
                for job in jobs
                if job.get("visit_plan_headline") in VISIT_PLAN_ATTENTION_HEADLINES
            ]
        ),
        "repeat_open_work": len(
            [
                job
                for job in jobs
                if int(job.get("operational_history_open_job_count") or 0) > 0
            ]
        ),
        "blocked": len([job for job in jobs if job.get("status") == JobStatus.blocked.value]),
    }


def derive_queue_priority(job: dict[str, object]) -> QueuePriorityProjection:
    if job.get("status") == JobStatus.blocked.value:
        return QueuePriorityProjection(
            label="Blocked coordination",
            summary="Site work is blocked and needs a rebooking, access fix, or escalation path.",
            rank=BLOCKED_QUEUE_PRIORITY_RANK,
        )
    if job.get("pending_signal_at") is not None:
        return QueuePriorityProjection(
            label="Waiting on response",
            summary=str(job.get("pending_signal_headline") or "A newer coordination signal needs follow-through."),
            rank=RESPONSE_NEEDED_QUEUE_PRIORITY_RANK,
        )
    if job.get("visit_plan_headline") in VISIT_PLAN_ATTENTION_HEADLINES:
        return QueuePriorityProjection(
            label="Visit plan at risk",
            summary=str(job.get("visit_plan_headline") or "Attendance planning is incomplete."),
            rank=VISIT_ATTENTION_QUEUE_PRIORITY_RANK,
        )
    if int(job.get("operational_history_open_job_count") or 0) > 0:
        return QueuePriorityProjection(
            label="Repeat work still open",
            summary=str(job.get("operational_history_headline") or "Related work at this location is still open."),
            rank=REPEAT_OPEN_QUEUE_PRIORITY_RANK,
        )
    if job.get("activity_gap_at") is not None:
        return QueuePriorityProjection(
            label="Progress update not reflected in state",
            summary=str(job.get("activity_gap_headline") or "A newer coordination update has not changed workflow state."),
            rank=STATE_GAP_QUEUE_PRIORITY_RANK,
        )
    return QueuePriorityProjection(
        label="Recently active",
        summary="No immediate coordination risk is ahead of the latest timeline activity.",
        rank=RECENT_ACTIVITY_QUEUE_PRIORITY_RANK,
    )


def _sortable_timestamp(value: object) -> float:
    if isinstance(value, datetime):
        return value.timestamp()
    return datetime(1970, 1, 1, tzinfo=timezone.utc).timestamp()


def queue_job_sort_key(job: dict[str, object]) -> tuple[int, float, float, str]:
    latest_event_at = _sortable_timestamp(job.get("latest_event_at") or job.get("updated_at"))
    latest_lifecycle_event_at = _sortable_timestamp(
        job.get("latest_lifecycle_event_at") or job.get("created_at")
    )
    return (
        int(job.get("queue_priority_rank") or RECENT_ACTIVITY_QUEUE_PRIORITY_RANK),
        -latest_event_at,
        -latest_lifecycle_event_at,
        str(job.get("id") or ""),
    )


def sort_jobs_for_queue(jobs: list[dict[str, object]]) -> list[dict[str, object]]:
    return sorted(jobs, key=queue_job_sort_key, reverse=False)


def serialize_related_job(job: Job, *, current_job: Job) -> dict[str, object]:
    projection = derive_coordination_projection(job, job.events)
    return {
        "id": job.id,
        "title": job.title,
        "status": projection.status.value,
        "status_label": status_label(projection.status),
        "coordination_headline": projection.headline,
        "reported_for_user_name": job_reported_for_name(job),
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "match_label": related_job_match_label(job, current_job=current_job),
    }


def report_created_event(job: Job) -> Event | None:
    for event in job.events:
        if event.event_type.value == "report_created":
            return event
    return None


def derive_report_intake(job: Job) -> ReportIntakeProjection:
    report_event = report_created_event(job)
    if report_event is None:
        return ReportIntakeProjection(
            channel=None,
            channel_label=None,
            summary=None,
            actor_label=None,
        )

    channel = report_event.reason_code
    actor = actor_label(report_event)
    reported_for_name = job_reported_for_name(job)
    channel_label = REPORT_CHANNEL_LABELS.get(channel, "Reported")
    if channel == ReportChannel.resident_portal.value:
        summary = f"{reported_for_name} reported this issue through the resident portal."
    elif channel == ReportChannel.staff_created.value:
        summary = f"{actor} logged this issue on behalf of {reported_for_name}."
    elif channel == ReportChannel.security_after_hours.value:
        summary = f"{actor} logged this issue through the after-hours path for {reported_for_name}."
    elif channel == ReportChannel.inspection_housekeeping.value:
        summary = f"{actor} logged this issue from an inspection or housekeeping round."
    else:
        summary = report_event.message

    return ReportIntakeProjection(
        channel=channel,
        channel_label=channel_label,
        summary=summary,
        actor_label=actor,
    )


def contractor_has_current_assignment(job: Job, user: User) -> bool:
    assignment = derive_assignment_projection(job, job.events)
    if assignment.assigned_contractor_user_id is not None:
        return assignment.assigned_contractor_user_id == user.id
    return bool(user.organisation_id and assignment.assigned_org_id == user.organisation_id)


def contractor_assigned_jobs(jobs: list[Job], user: User) -> list[Job]:
    return [job for job in jobs if contractor_has_current_assignment(job, user)]


def contractor_can_view_job(job: Job, user: User) -> bool:
    if contractor_has_current_assignment(job, user):
        return True

    for event in job.events:
        if event.actor_user_id == user.id or event.assigned_contractor_user_id == user.id:
            return True
        if user.organisation_id is None:
            continue
        if event.actor_org_id == user.organisation_id or event.assigned_org_id == user.organisation_id:
            return True
    return False


def can_view_job(job: Job, user: User) -> bool:
    if user.role in OPERATIONS_ROLES:
        return bool(user.organisation_id and job.organisation_id == user.organisation_id)
    if user.role == UserRole.resident:
        return bool(
            user.organisation_id
            and job.reported_for_user_id == user.id
            and job.organisation_id == user.organisation_id
        )
    if user.role != UserRole.contractor:
        return False
    return contractor_can_view_job(job, user)


def visible_job(session: Session, user: User, job_id: uuid.UUID) -> Job:
    job = session.scalar(job_query().where(Job.id == job_id).limit(1))
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if not can_view_job(job, user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot access this job")
    return job


def visible_events(session: Session, job_id: uuid.UUID) -> list[Event]:
    return list(session.scalars(event_query(job_id)))


def job_activity_sort_key(job: Job) -> tuple[datetime, datetime, uuid.UUID]:
    projection = derive_coordination_projection(job, job.events)
    latest_event_at = projection.latest_event_at or job.created_at
    latest_lifecycle_event_at = projection.latest_lifecycle_event_at or job.created_at
    return latest_event_at, latest_lifecycle_event_at, job.id


def visible_jobs(
    session: Session,
    user: User,
    *,
    mine: bool = False,
    assigned: bool = False,
) -> list[Job]:
    stmt = job_query()

    if user.role in OPERATIONS_ROLES:
        if user.organisation_id is None:
            return []
        stmt = stmt.where(Job.organisation_id == user.organisation_id)
    elif mine or user.role == UserRole.resident:
        if user.organisation_id is None:
            return []
        stmt = stmt.where(Job.reported_for_user_id == user.id, Job.organisation_id == user.organisation_id)
    else:
        jobs = list(session.scalars(stmt))
        visible = [job for job in jobs if contractor_can_view_job(job, user)]
        visible.sort(key=job_activity_sort_key, reverse=True)
        if assigned:
            return contractor_assigned_jobs(visible, user)
        return visible

    jobs = list(session.scalars(stmt))
    if assigned:
        jobs = [job for job in jobs if derive_assignment_projection(job, job.events).assignee_label is not None]
    jobs.sort(key=job_activity_sort_key, reverse=True)
    return jobs


def related_jobs_for_user(
    session: Session,
    user: User,
    *,
    job: Job,
    limit: int = 5,
) -> list[dict[str, object]]:
    matching_jobs = related_job_records_for_user(session, user, job=job)
    return [serialize_related_job(candidate, current_job=job) for candidate in matching_jobs[:limit]]


def related_job_records_for_user(
    session: Session,
    user: User,
    *,
    job: Job,
) -> list[Job]:
    related_jobs = [candidate for candidate in visible_jobs(session, user) if candidate.id != job.id]
    matching_jobs = [candidate for candidate in related_jobs if jobs_share_location_context(candidate, current_job=job)]
    matching_jobs.sort(
        key=lambda candidate: related_job_sort_key(candidate, current_job=job),
        reverse=True,
    )
    return matching_jobs


def location_parent_id(job: Job) -> uuid.UUID | None:
    location = getattr(job, "location", None)
    if location is None:
        return None
    return getattr(location, "parent_id", None)


def jobs_share_location_context(candidate: Job, *, current_job: Job) -> bool:
    if candidate.location_id == current_job.location_id:
        return True

    current_parent_id = location_parent_id(current_job)
    candidate_parent_id = location_parent_id(candidate)
    if current_parent_id is None or candidate_parent_id is None:
        return False

    return current_parent_id == candidate_parent_id


def related_job_match_label(job: Job, *, current_job: Job) -> str:
    if current_job.asset_id is not None and job.asset_id == current_job.asset_id:
        return "Same asset"
    if job.location_id == current_job.location_id:
        return "Same location"
    if jobs_share_location_context(job, current_job=current_job):
        return "Same parent area"
    return "Related location context"


def related_job_sort_key(job: Job, *, current_job: Job) -> tuple[bool, bool, datetime, datetime, uuid.UUID]:
    activity_sort = job_activity_sort_key(job)
    return (
        current_job.asset_id is not None and job.asset_id == current_job.asset_id,
        job.location_id == current_job.location_id,
        activity_sort[0],
        activity_sort[1],
        activity_sort[2],
    )


def operational_history_for_user(
    session: Session,
    user: User,
    *,
    job: Job,
) -> OperationalHistoryProjection:
    related_jobs = related_job_records_for_user(session, user, job=job)
    location_job_count = len(related_jobs)
    exact_location_job_count = len([candidate for candidate in related_jobs if candidate.location_id == job.location_id])
    nearby_area_job_count = location_job_count - exact_location_job_count
    asset_job_count = (
        len([candidate for candidate in related_jobs if job.asset_id is not None and candidate.asset_id == job.asset_id])
        if job.asset_id is not None
        else 0
    )
    open_asset_job_count = (
        len(
            [
                candidate
                for candidate in related_jobs
                if job.asset_id is not None
                and candidate.asset_id == job.asset_id
                and derive_coordination_projection(candidate, candidate.events).status not in RESOLVED_JOB_STATUSES
            ]
        )
        if job.asset_id is not None
        else 0
    )
    open_job_count = len(
        [
            candidate
            for candidate in related_jobs
            if derive_coordination_projection(candidate, candidate.events).status not in RESOLVED_JOB_STATUSES
        ]
    )

    if location_job_count == 0:
        return OperationalHistoryProjection(
            headline="No other visible operational history at this location",
            summary="This is the only visible record here so far, so coordination will start from this timeline.",
            location_job_count=0,
            asset_job_count=0,
            open_job_count=0,
        )

    latest_related = related_jobs[0]
    latest_related_projection = derive_coordination_projection(latest_related, latest_related.events)
    if asset_job_count > 0:
        headline = "Repeat issue risk on this asset"
    elif exact_location_job_count > 0:
        headline = "Repeat issue risk at this location"
    else:
        headline = "Related operational history in this area"

    if nearby_area_job_count == 0 and job.asset_id is not None:
        scope_summary = (
            f"{location_job_count} other visible job(s) here, including {asset_job_count} on this asset. "
            f"{open_asset_job_count} related asset job(s) are still open."
        )
    elif nearby_area_job_count == 0:
        scope_summary = (
            f"{location_job_count} other visible job(s) here; this job has no asset selected so repeat checks stay "
            "location-based"
        )
    elif job.asset_id is not None:
        scope_summary = (
            f"{exact_location_job_count} other visible job(s) at this exact location and {nearby_area_job_count} "
            f"more in the same parent area. {asset_job_count} related job(s) are on this asset. "
            f"{open_asset_job_count} related asset job(s) are still open."
        )
    else:
        scope_summary = (
            f"{exact_location_job_count} other visible job(s) at this exact location and {nearby_area_job_count} "
            "more in the same parent area; this job has no asset selected so repeat checks stay location-based."
        )

    return OperationalHistoryProjection(
        headline=headline,
        summary=(
            f"{scope_summary} {open_job_count} related job(s) are still open. "
            f"Latest related record: {latest_related.title} ({status_label(latest_related_projection.status)})."
        ),
        location_job_count=location_job_count,
        asset_job_count=asset_job_count,
        open_job_count=open_job_count,
    )


def serialize_job_with_history(
    session: Session,
    user: User,
    *,
    job: Job,
) -> dict[str, object]:
    return serialize_job_for_user(session, user, job=job, include_history=True)


def render_page(
    *,
    request: Request,
    session: Session,
    current_user: User,
    template_name: str,
    **context: object,
) -> HTMLResponse:
    demo_mode = request.app.state.settings.demo_mode
    base_context = {
        "request": request,
        "current_user": serialize_user(current_user),
        "home_path": home_path_for(current_user.role),
        "nav_links": navigation_for(current_user),
        "demo_mode": demo_mode,
        "demo_users": [serialize_demo_user(user) for user in list_demo_users(session)] if demo_mode else [],
    }
    base_context.update(context)
    return templates.TemplateResponse(request=request, name=template_name, context=base_context)


def render_login_page(
    *,
    request: Request,
    session: Session,
    auth_error: str | None = None,
    next_path: str = "/",
    email_value: str = "",
    status_code: int = 200,
) -> HTMLResponse:
    demo_mode = request.app.state.settings.demo_mode
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        status_code=status_code,
        context={
            "request": request,
            "auth_error": auth_error,
            "next_path": next_path,
            "email_value": email_value,
            "demo_mode": demo_mode,
            "demo_password": request.app.state.settings.demo_password if demo_mode else None,
            "demo_users": [serialize_demo_user(user) for user in list_demo_users(session)] if demo_mode else [],
        },
    )


def list_contractor_organisations(session: Session) -> list[dict[str, object]]:
    return [
        {
            "id": organisation.id,
            "name": organisation.name,
            "contractor_mode": organisation.contractor_mode.value if organisation.contractor_mode else None,
        }
        for organisation in session.scalars(
            select(Organisation)
            .where(Organisation.type == OrganisationType.contractor)
            .order_by(Organisation.name.asc())
        )
    ]


def list_contractor_users(session: Session, *, include_demo: bool) -> list[dict[str, object]]:
    stmt = (
        select(User)
        .join(User.organisation)
        .options(joinedload(User.organisation))
        .where(
            User.role == UserRole.contractor,
            Organisation.type == OrganisationType.contractor,
        )
        .order_by(User.name.asc())
    )
    if not include_demo:
        stmt = stmt.where(User.is_demo_account.is_(False))
    return [
        {
            "id": user.id,
            "name": user.name,
            "organisation_id": user.organisation_id,
            "organisation_name": user.organisation.name if user.organisation else None,
        }
        for user in session.scalars(stmt)
    ]


def list_resident_users(session: Session, *, organisation_id, include_demo: bool) -> list[dict[str, object]]:
    stmt = (
        select(User)
        .where(
            User.role == UserRole.resident,
            User.organisation_id == organisation_id,
        )
        .order_by(User.name.asc())
    )
    if not include_demo:
        stmt = stmt.where(User.is_demo_account.is_(False))
    return [
        {
            "id": user.id,
            "name": user.name,
            "email": user.email,
        }
        for user in session.scalars(stmt)
    ]
