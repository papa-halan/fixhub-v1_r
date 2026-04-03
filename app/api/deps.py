from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.core.security import verify_session_token
from app.models import (
    Event,
    Job,
    JobStatus,
    Organisation,
    OrganisationType,
    User,
    UserRole,
)
from app.services import OPERATIONS_ROLES, assignee_label, assignee_scope, list_demo_users, role_label
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
            joinedload(Job.organisation),
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
            joinedload(Event.job).joinedload(Job.organisation),
            joinedload(Event.job).joinedload(Job.location),
            joinedload(Event.job).joinedload(Job.asset),
            joinedload(Event.job).joinedload(Job.assigned_org),
            joinedload(Event.job).joinedload(Job.assigned_contractor).joinedload(User.organisation),
            joinedload(Event.actor_user).joinedload(User.organisation),
            joinedload(Event.actor_org),
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
        return bool(request.state.invalid_session), request.state.current_user

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
        return [{"label": "Operations Queue", "href": "/admin/jobs"}]
    return [{"label": "Assigned Work", "href": "/contractor/jobs"}]


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
    if event.actor_user:
        return user_role_label(event.actor_user)
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
        "role_label": user_role_label(user),
        "organisation_id": organisation.id if organisation else None,
        "organisation_name": organisation.name if organisation else None,
        "organisation_type": organisation.type.value if organisation else None,
        "created_at": user.created_at,
    }


def job_location_name(job: Job) -> str:
    assert job.location is not None
    return job.location.name


def job_asset_name(job: Job) -> str | None:
    if job.asset:
        return job.asset.name
    return None


def serialize_job(job: Job) -> dict[str, object]:
    scope = assignee_scope(job)
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
        "status": job.status.value,
        "status_label": status_label(job.status),
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


def can_view_job(job: Job, user: User) -> bool:
    if user.role in OPERATIONS_ROLES:
        return bool(user.organisation_id and job.organisation_id == user.organisation_id)
    if user.role == UserRole.resident:
        return bool(user.organisation_id and job.created_by == user.id and job.organisation_id == user.organisation_id)
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
    stmt = job_query()

    if user.role in OPERATIONS_ROLES:
        if user.organisation_id is None:
            return []
        stmt = stmt.where(Job.organisation_id == user.organisation_id)
    elif mine or user.role == UserRole.resident:
        if user.organisation_id is None:
            return []
        stmt = stmt.where(Job.created_by == user.id, Job.organisation_id == user.organisation_id)
    else:
        contractor_filters = [Job.assigned_contractor_user_id == user.id]
        if user.organisation_id is not None:
            contractor_filters.append(Job.assigned_org_id == user.organisation_id)
        stmt = stmt.where(or_(*contractor_filters))

    if assigned:
        stmt = stmt.where(or_(Job.assigned_org_id.is_not(None), Job.assigned_contractor_user_id.is_not(None)))

    return list(session.scalars(stmt))


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
        .options(joinedload(User.organisation))
        .where(User.role == UserRole.contractor)
        .order_by(User.name.asc())
    )
    if not include_demo:
        stmt = stmt.where(User.is_demo_account.is_(False))
    return [
        {
            "id": user.id,
            "name": user.name,
            "organisation_name": user.organisation.name if user.organisation else None,
        }
        for user in session.scalars(stmt)
    ]
