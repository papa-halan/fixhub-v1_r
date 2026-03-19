from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    Event,
    EventType,
    Job,
    JobStatus,
    Organisation,
    OrganisationType,
    OwnerScope,
    ResponsibilityOwner,
    ResponsibilityStage,
    User,
    UserRole,
)
from app.services import list_demo_users


APP_DIR = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))


def format_timestamp(value: datetime) -> str:
    return value.astimezone().strftime("%d %b %H:%M")


templates.env.filters["timestamp"] = format_timestamp


OPERATIONS_ROLES = (
    UserRole.admin,
    UserRole.reception_admin,
    UserRole.triage_officer,
    UserRole.coordinator,
)
ASSIGNMENT_ROLES = (UserRole.admin, UserRole.coordinator)
TRIAGE_ROLES = (UserRole.admin, UserRole.triage_officer)
COORDINATION_ROLES = (UserRole.admin, UserRole.coordinator)
ROLE_HOMES = {
    UserRole.resident: "/resident/report",
    UserRole.admin: "/admin/jobs",
    UserRole.reception_admin: "/admin/jobs",
    UserRole.triage_officer: "/admin/jobs",
    UserRole.coordinator: "/admin/jobs",
    UserRole.contractor: "/contractor/jobs",
}
STATUS_EVENT_MESSAGES = {
    JobStatus.new: "Moved job back to new",
    JobStatus.assigned: "Marked job assigned",
    JobStatus.triaged: "Marked job triaged",
    JobStatus.scheduled: "Scheduled site visit",
    JobStatus.in_progress: "Marked job in progress",
    JobStatus.on_hold: "Placed job on hold",
    JobStatus.blocked: "Marked job blocked",
    JobStatus.completed: "Marked job completed",
    JobStatus.cancelled: "Cancelled job",
    JobStatus.reopened: "Reopened job",
    JobStatus.follow_up_scheduled: "Scheduled follow-up visit",
    JobStatus.escalated: "Escalated job for review",
}
ASSIGNEE_REQUIRED_STATUSES = {
    JobStatus.assigned,
    JobStatus.scheduled,
    JobStatus.in_progress,
    JobStatus.blocked,
    JobStatus.completed,
    JobStatus.follow_up_scheduled,
}
REASON_REQUIRED_STATUSES = {
    JobStatus.on_hold,
    JobStatus.blocked,
    JobStatus.cancelled,
    JobStatus.reopened,
    JobStatus.follow_up_scheduled,
    JobStatus.escalated,
}
DEFAULT_STAGE_BY_STATUS = {
    JobStatus.new: ResponsibilityStage.reception,
    JobStatus.assigned: ResponsibilityStage.triage,
    JobStatus.triaged: ResponsibilityStage.triage,
    JobStatus.scheduled: ResponsibilityStage.coordination,
    JobStatus.in_progress: ResponsibilityStage.execution,
    JobStatus.on_hold: ResponsibilityStage.coordination,
    JobStatus.blocked: ResponsibilityStage.execution,
    JobStatus.completed: ResponsibilityStage.execution,
    JobStatus.cancelled: ResponsibilityStage.coordination,
    JobStatus.reopened: ResponsibilityStage.triage,
    JobStatus.follow_up_scheduled: ResponsibilityStage.coordination,
    JobStatus.escalated: ResponsibilityStage.triage,
}
EVENT_TYPE_BY_STATUS = {
    JobStatus.assigned: EventType.assignment,
    JobStatus.scheduled: EventType.schedule,
    JobStatus.completed: EventType.completion,
    JobStatus.follow_up_scheduled: EventType.follow_up,
    JobStatus.escalated: EventType.escalation,
}
ALLOWED_STATUS_CHANGES = {
    JobStatus.new: {JobStatus.assigned, JobStatus.triaged, JobStatus.cancelled},
    JobStatus.assigned: {JobStatus.triaged, JobStatus.on_hold, JobStatus.cancelled, JobStatus.escalated},
    JobStatus.triaged: {
        JobStatus.assigned,
        JobStatus.scheduled,
        JobStatus.on_hold,
        JobStatus.cancelled,
        JobStatus.escalated,
    },
    JobStatus.scheduled: {
        JobStatus.in_progress,
        JobStatus.on_hold,
        JobStatus.cancelled,
        JobStatus.escalated,
    },
    JobStatus.in_progress: {
        JobStatus.blocked,
        JobStatus.on_hold,
        JobStatus.completed,
        JobStatus.escalated,
    },
    JobStatus.on_hold: {
        JobStatus.triaged,
        JobStatus.scheduled,
        JobStatus.cancelled,
        JobStatus.escalated,
    },
    JobStatus.blocked: {
        JobStatus.scheduled,
        JobStatus.in_progress,
        JobStatus.on_hold,
        JobStatus.cancelled,
        JobStatus.escalated,
    },
    JobStatus.completed: {JobStatus.reopened, JobStatus.follow_up_scheduled},
    JobStatus.cancelled: set(),
    JobStatus.reopened: {
        JobStatus.triaged,
        JobStatus.scheduled,
        JobStatus.on_hold,
        JobStatus.cancelled,
        JobStatus.escalated,
    },
    JobStatus.follow_up_scheduled: {
        JobStatus.in_progress,
        JobStatus.completed,
        JobStatus.reopened,
        JobStatus.cancelled,
        JobStatus.escalated,
    },
    JobStatus.escalated: {
        JobStatus.triaged,
        JobStatus.scheduled,
        JobStatus.on_hold,
        JobStatus.cancelled,
    },
}
ROLE_GROUPS_BY_TARGET = {
    JobStatus.assigned: ASSIGNMENT_ROLES,
    JobStatus.triaged: TRIAGE_ROLES,
    JobStatus.scheduled: TRIAGE_ROLES,
    JobStatus.in_progress: (UserRole.contractor,),
    JobStatus.on_hold: (*TRIAGE_ROLES, *COORDINATION_ROLES, UserRole.contractor),
    JobStatus.blocked: (UserRole.contractor,),
    JobStatus.completed: (UserRole.contractor, UserRole.admin),
    JobStatus.cancelled: COORDINATION_ROLES,
    JobStatus.reopened: COORDINATION_ROLES,
    JobStatus.follow_up_scheduled: TRIAGE_ROLES,
    JobStatus.escalated: COORDINATION_ROLES,
    JobStatus.new: ASSIGNMENT_ROLES,
}


@dataclass(frozen=True)
class EventSpec:
    message: str
    event_type: EventType
    reason_code: str | None = None
    responsibility_stage: ResponsibilityStage | None = None
    owner_scope: OwnerScope | None = None
    responsibility_owner: ResponsibilityOwner | None = None


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
            joinedload(Job.location),
            joinedload(Job.asset),
            joinedload(Job.assigned_org),
            joinedload(Job.assigned_contractor).joinedload(User.organisation),
        )
        .order_by(Job.updated_at.desc(), Job.created_at.desc())
    )


def event_query(job_id: uuid.UUID):
    return (
        select(Event)
        .where(Event.job_id == job_id)
        .options(
            joinedload(Event.job).joinedload(Job.location),
            joinedload(Event.job).joinedload(Job.asset),
            joinedload(Event.job).joinedload(Job.assigned_org),
            joinedload(Event.job).joinedload(Job.assigned_contractor).joinedload(User.organisation),
            joinedload(Event.actor_user).joinedload(User.organisation),
            joinedload(Event.actor_org),
            joinedload(Event.location_record),
            joinedload(Event.asset),
        )
        .order_by(Event.created_at.asc())
    )


def current_selector(request: Request) -> str | None:
    if request.url.path.startswith("/api"):
        return getattr(request.state, "api_user_email", None)

    query_user = (request.query_params.get("as_user") or "").strip()
    if query_user:
        return query_user

    header_user = (request.headers.get("X-User-Email") or "").strip()
    if header_user:
        return header_user

    cookie_user = (request.cookies.get("fixhub_user") or "").strip()
    if cookie_user:
        return cookie_user

    return None


def lookup_current_user(
    request: Request,
    session: Session,
) -> tuple[str | None, User | None]:
    selector = current_selector(request)
    if selector is None:
        return None, None
    user = session.scalar(user_query().where(User.email == selector).limit(1))
    return selector, user


def get_current_user(
    request: Request,
    session: Session = Depends(get_session),
) -> User:
    selector, user = lookup_current_user(request, session)
    if selector is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown user")
    return user


def require_role(user: User, *roles: UserRole) -> None:
    if user.role not in roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot access this page")


def role_label(role: UserRole | str | None) -> str | None:
    if role is None:
        return None
    role_value = role.value if isinstance(role, UserRole) else role
    return role_value.replace("_", " ").title()


def home_path_for(role: UserRole) -> str:
    return ROLE_HOMES[role]


def navigation_for(user: User) -> list[dict[str, str]]:
    if user.role == UserRole.resident:
        return [
            {"label": "Report Issue", "href": "/resident/report"},
            {"label": "My Reports", "href": "/resident/jobs"},
        ]
    if user.role in OPERATIONS_ROLES:
        return [{"label": "Operations Job List", "href": "/admin/jobs"}]
    return [{"label": "Assigned Jobs", "href": "/contractor/jobs"}]


def actor_name(event: Event) -> str:
    if event.actor_user:
        return event.actor_user.name
    if event.actor_org:
        return event.actor_org.name
    return "System"


def actor_role_value(event: Event) -> str | None:
    if event.actor_user:
        return event.actor_user.role.value
    return None


def actor_role_label(event: Event) -> str | None:
    return role_label(actor_role_value(event))


def organisation_name(event: Event) -> str | None:
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
        "organisation_id": organisation.id if organisation else None,
        "organisation_name": organisation.name if organisation else None,
        "organisation_type": organisation.type.value if organisation else None,
        "created_at": user.created_at,
    }


def job_location_name(job: Job) -> str:
    assert job.location_id is not None
    assert job.location is not None
    return job.location.name


def job_asset_name(job: Job) -> str | None:
    if job.asset:
        return job.asset.name
    return None


def job_has_assignee(job: Job) -> bool:
    return job.assigned_org_id is not None or job.assigned_contractor_user_id is not None


def assignee_scope(job: Job) -> OwnerScope | None:
    if job.assigned_contractor_user_id is not None:
        return OwnerScope.user
    if job.assigned_org_id is not None:
        return OwnerScope.organisation
    return None


def assignee_label(job: Job) -> str | None:
    if job.assigned_contractor is not None:
        return job.assigned_contractor.name
    if job.assigned_org is not None:
        return job.assigned_org.name
    return None


def serialize_job(job: Job) -> dict[str, object]:
    assert job.location_id is not None
    scope = assignee_scope(job)
    return {
        "id": job.id,
        "title": job.title,
        "description": job.description,
        "location": job_location_name(job),
        "location_id": job.location_id,
        "asset_id": job.asset_id,
        "asset_name": job_asset_name(job),
        "status": job.status.value,
        "status_label": role_label(job.status.value),
        "created_by": job.created_by,
        "created_by_name": job.creator.name,
        "assigned_org_id": job.assigned_org_id,
        "assigned_org_name": job.assigned_org.name if job.assigned_org else None,
        "assigned_contractor_user_id": job.assigned_contractor_user_id,
        "assigned_contractor_name": job.assigned_contractor.name if job.assigned_contractor else None,
        "assignee_scope": scope.value if scope else None,
        "assignee_label": assignee_label(job),
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


def event_location_name(event: Event) -> str | None:
    if event.location_record:
        return event.location_record.name
    if event.job:
        return job_location_name(event.job)
    return None


def event_asset_name(event: Event) -> str | None:
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
        "actor_label": actor_label(event),
        "event_type": event.event_type.value,
        "message": event.message,
        "reason_code": event.reason_code,
        "responsibility_stage": event.responsibility_stage.value if event.responsibility_stage else None,
        "owner_scope": event.owner_scope.value if event.owner_scope else None,
        "responsibility_owner": event.responsibility_owner.value if event.responsibility_owner else None,
        "created_at": event.created_at,
    }


def serialize_switch_user(user: User) -> dict[str, str]:
    return {
        "email": user.email,
        "label": user.name,
        "role": user.role.value,
        "home_path": home_path_for(user.role),
    }


def build_job_counts(jobs: list[dict[str, object]]) -> dict[str, int]:
    counts = {status.value: 0 for status in JobStatus}
    counts["total"] = len(jobs)
    for job in jobs:
        counts[str(job["status"])] += 1
    return counts


def can_view_job(job: Job, user: User) -> bool:
    if job.location_id is None or job.location is None:
        return False
    if user.role in OPERATIONS_ROLES:
        return bool(user.organisation_id and job.location.organisation_id == user.organisation_id)
    if user.role == UserRole.resident:
        return bool(
            user.organisation_id
            and job.created_by == user.id
            and job.location.organisation_id == user.organisation_id
        )
    if user.role != UserRole.contractor:
        return False
    if job.assigned_contractor_user_id == user.id:
        return True
    return bool(user.organisation_id and job.assigned_org_id == user.organisation_id)


def visible_job(session: Session, user: User, job_id: uuid.UUID) -> Job:
    job = session.scalar(job_query().where(Job.id == job_id).limit(1))
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if not can_view_job(job, user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot access this job")
    return job


def visible_events(session: Session, job_id: uuid.UUID) -> list[Event]:
    return list(session.scalars(event_query(job_id)))


def visible_jobs(
    session: Session,
    user: User,
    *,
    mine: bool = False,
    assigned: bool = False,
) -> list[Job]:
    stmt = job_query().where(Job.location_id.is_not(None))

    if user.role in OPERATIONS_ROLES:
        if user.organisation_id is None:
            return []
        stmt = stmt.where(Job.location.has(organisation_id=user.organisation_id))
    elif mine or user.role == UserRole.resident:
        if user.organisation_id is None:
            return []
        stmt = stmt.where(
            Job.created_by == user.id,
            Job.location.has(organisation_id=user.organisation_id),
        )
    else:
        contractor_filters = [Job.assigned_contractor_user_id == user.id]
        if user.organisation_id is not None:
            contractor_filters.append(Job.assigned_org_id == user.organisation_id)
        stmt = stmt.where(or_(*contractor_filters))

    if assigned:
        stmt = stmt.where(
            or_(Job.assigned_org_id.is_not(None), Job.assigned_contractor_user_id.is_not(None))
        )

    return list(session.scalars(stmt))


def touch_job(job: Job) -> None:
    job.updated_at = datetime.now(timezone.utc)


def default_responsibility_owner(actor: User) -> ResponsibilityOwner:
    if actor.role == UserRole.reception_admin:
        return ResponsibilityOwner.reception_admin
    if actor.role == UserRole.triage_officer:
        return ResponsibilityOwner.triage_officer
    if actor.role in {UserRole.admin, UserRole.coordinator}:
        return ResponsibilityOwner.coordinator
    if actor.role == UserRole.contractor:
        return ResponsibilityOwner.contractor
    return ResponsibilityOwner.resident


def default_stage_for_actor(actor: User) -> ResponsibilityStage:
    if actor.role in {UserRole.resident, UserRole.reception_admin}:
        return ResponsibilityStage.reception
    if actor.role == UserRole.triage_officer:
        return ResponsibilityStage.triage
    if actor.role in {UserRole.admin, UserRole.coordinator}:
        return ResponsibilityStage.coordination
    return ResponsibilityStage.execution


def default_owner_scope(actor: User, job: Job) -> OwnerScope:
    scope = assignee_scope(job)
    if scope is not None and job.status in ASSIGNEE_REQUIRED_STATUSES:
        return scope
    if actor.role == UserRole.resident or actor.organisation_id is None:
        return OwnerScope.user
    return OwnerScope.organisation


def append_event(
    session: Session,
    *,
    job: Job,
    actor: User,
    message: str,
    event_type: EventType = EventType.note,
    reason_code: str | None = None,
    responsibility_stage: ResponsibilityStage | None = None,
    owner_scope: OwnerScope | None = None,
    responsibility_owner: ResponsibilityOwner | None = None,
) -> Event:
    touch_job(job)
    assert job.location_id is not None
    event = Event(
        job_id=job.id,
        actor_user_id=actor.id,
        actor_org_id=actor.organisation_id,
        location_id=job.location_id,
        asset_id=job.asset_id,
        event_type=event_type,
        message=message,
        reason_code=reason_code,
        responsibility_stage=responsibility_stage or default_stage_for_actor(actor),
        owner_scope=owner_scope or default_owner_scope(actor, job),
        responsibility_owner=responsibility_owner or default_responsibility_owner(actor),
        created_at=datetime.now(timezone.utc),
    )
    session.add(event)
    session.flush()
    session.refresh(event)
    return event


def require_status_permission(actor: User, target: JobStatus) -> None:
    if actor.role == UserRole.resident:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Residents cannot change job status")
    allowed_roles = ROLE_GROUPS_BY_TARGET[target]
    if actor.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"{role_label(actor.role)} cannot move a job to {target.value}",
        )


def fallback_status_for_unassigned(job: Job) -> JobStatus:
    if job.status in {JobStatus.new, JobStatus.assigned}:
        return JobStatus.new
    return JobStatus.triaged


def validate_assignee_required(job: Job, target: JobStatus) -> None:
    if target in ASSIGNEE_REQUIRED_STATUSES and not job_has_assignee(job):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"{target.value} requires an assignee",
        )


def apply_status_change(
    job: Job,
    target: JobStatus,
    actor: User,
    *,
    reason_code: str | None = None,
    responsibility_stage: ResponsibilityStage | None = None,
    owner_scope: OwnerScope | None = None,
) -> EventSpec | None:
    require_status_permission(actor, target)

    if target == job.status:
        return None

    if target not in ALLOWED_STATUS_CHANGES[job.status]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot move job from {job.status.value} to {target.value}",
        )

    validate_assignee_required(job, target)

    if target in REASON_REQUIRED_STATUSES and reason_code is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"reason_code is required when moving a job to {target.value}",
        )

    if target == JobStatus.completed and actor.role != UserRole.contractor and reason_code is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="reason_code is required when an operations user completes a job",
        )

    stage = responsibility_stage or (
        default_stage_for_actor(actor)
        if target == JobStatus.completed and actor.role != UserRole.contractor
        else DEFAULT_STAGE_BY_STATUS[target]
    )
    if stage is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"responsibility_stage is required when moving a job to {target.value}",
        )

    job.status = target
    return EventSpec(
        message=STATUS_EVENT_MESSAGES[target],
        event_type=EVENT_TYPE_BY_STATUS.get(target, EventType.status_change),
        reason_code=reason_code,
        responsibility_stage=stage,
        owner_scope=owner_scope or default_owner_scope(actor, job),
        responsibility_owner=default_responsibility_owner(actor),
    )


def render_page(
    *,
    request: Request,
    session: Session,
    current_user: User,
    template_name: str,
    **context: object,
) -> HTMLResponse:
    base_context = {
        "request": request,
        "current_user": serialize_user(current_user),
        "home_path": home_path_for(current_user.role),
        "nav_links": navigation_for(current_user),
        "demo_users": [serialize_switch_user(user) for user in list_demo_users(session)],
    }
    base_context.update(context)
    return templates.TemplateResponse(request=request, name=template_name, context=base_context)


def render_login_page(
    *,
    request: Request,
    session: Session,
    invalid_user: bool = False,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "request": request,
            "demo_users": [serialize_switch_user(user) for user in list_demo_users(session)],
            "invalid_user": invalid_user,
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


def list_contractor_users(session: Session) -> list[dict[str, object]]:
    return [
        {
            "id": user.id,
            "name": user.name,
            "organisation_name": user.organisation.name if user.organisation else None,
        }
        for user in session.scalars(
            select(User)
            .options(joinedload(User.organisation))
            .where(User.role == UserRole.contractor)
            .order_by(User.name.asc())
        )
    ]
