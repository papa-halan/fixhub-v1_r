from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.database import build_engine, build_session_factory
from app.models import Base, Event, Job, JobStatus, Organisation, OrganisationType, User, UserRole
from app.services import ensure_demo_data, list_demo_users


BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def format_timestamp(value: datetime) -> str:
    return value.astimezone().strftime("%d %b %H:%M")


templates.env.filters["timestamp"] = format_timestamp

ROLE_HOMES = {
    UserRole.resident: "/resident/report",
    UserRole.admin: "/admin/jobs",
    UserRole.contractor: "/contractor/jobs",
}

STATUS_EVENT_MESSAGES = {
    JobStatus.new: "Moved job back to new",
    JobStatus.assigned: "Marked job assigned",
    JobStatus.in_progress: "Marked job in progress",
    JobStatus.completed: "Marked job completed",
}

ALLOWED_STATUS_CHANGES = {
    JobStatus.new: {JobStatus.assigned},
    JobStatus.assigned: {JobStatus.in_progress, JobStatus.completed},
    JobStatus.in_progress: {JobStatus.completed},
    JobStatus.completed: set(),
}


class JobCreateIn(BaseModel):
    title: str
    description: str
    location: str


class JobPatchIn(BaseModel):
    assigned_org_id: uuid.UUID | None = None
    status: JobStatus | None = None


class EventCreateIn(BaseModel):
    message: str


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
            joinedload(Job.assigned_org),
        )
        .order_by(Job.updated_at.desc(), Job.created_at.desc())
    )


def event_query(job_id: uuid.UUID):
    return (
        select(Event)
        .where(Event.job_id == job_id)
        .options(
            joinedload(Event.actor_user).joinedload(User.organisation),
            joinedload(Event.actor_org),
        )
        .order_by(Event.created_at.asc())
    )


def current_selector(request: Request) -> str | None:
    if request.url.path.startswith("/api"):
        return getattr(request.state, "api_user_email", None)
    return (
        request.query_params.get("as_user")
        or request.headers.get("X-User-Email")
        or request.cookies.get("fixhub_user")
        or settings.default_user_email
    )


def get_current_user(
    request: Request,
    session: Session = Depends(get_session),
) -> User:
    selector = current_selector(request)
    if selector is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user = session.scalar(user_query().where(User.email == selector).limit(1))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown user")
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
    if user.role == UserRole.admin:
        return [{"label": "Admin Job List", "href": "/admin/jobs"}]
    return [{"label": "Contractor Job List", "href": "/contractor/jobs"}]


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
    role = actor_role_value(event)
    if role is None:
        return None
    return role.replace("_", " ").title()


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


def serialize_job(job: Job) -> dict[str, object]:
    return {
        "id": job.id,
        "title": job.title,
        "description": job.description,
        "location": job.location,
        "status": job.status.value,
        "status_label": job.status.value.replace("_", " ").title(),
        "created_by": job.created_by,
        "created_by_name": job.creator.name,
        "assigned_org_id": job.assigned_org_id,
        "assigned_org_name": job.assigned_org.name if job.assigned_org else None,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


def serialize_event(event: Event) -> dict[str, object]:
    role = actor_role_value(event)
    return {
        "id": event.id,
        "job_id": event.job_id,
        "actor_user_id": event.actor_user_id,
        "actor_org_id": event.actor_org_id,
        "actor_name": actor_name(event),
        "actor_role": role,
        "actor_role_label": actor_role_label(event),
        "organisation_name": organisation_name(event),
        "actor_label": actor_label(event),
        "message": event.message,
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
    if user.role == UserRole.admin:
        return True
    if user.role == UserRole.resident:
        return job.created_by == user.id
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

    if mine or user.role == UserRole.resident:
        stmt = stmt.where(Job.created_by == user.id)

    if assigned:
        if user.role == UserRole.contractor:
            if user.organisation_id is None:
                return []
            stmt = stmt.where(Job.assigned_org_id == user.organisation_id)
        else:
            stmt = stmt.where(Job.assigned_org_id.is_not(None))
    elif user.role == UserRole.contractor:
        if user.organisation_id is None:
            return []
        stmt = stmt.where(Job.assigned_org_id == user.organisation_id)

    return list(session.scalars(stmt))


def touch_job(job: Job) -> None:
    job.updated_at = datetime.now(timezone.utc)


def append_event(session: Session, *, job: Job, actor: User, message: str) -> Event:
    touch_job(job)
    event = Event(
        job_id=job.id,
        actor_user_id=actor.id,
        actor_org_id=actor.organisation_id,
        message=message,
        created_at=datetime.now(timezone.utc),
    )
    session.add(event)
    session.flush()
    session.refresh(event)
    return event


def apply_status_change(job: Job, target: JobStatus, actor: User) -> str | None:
    if actor.role == UserRole.resident:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Residents cannot change job status")

    if actor.role == UserRole.contractor and target not in {JobStatus.in_progress, JobStatus.completed}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Contractors can only progress assigned jobs")

    if target == job.status:
        return None

    if target == JobStatus.assigned and job.assigned_org_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assign a contractor before marking a job as assigned")

    if target not in ALLOWED_STATUS_CHANGES[job.status]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot move job from {job.status.value} to {target.value}",
        )

    job.status = target
    return STATUS_EVENT_MESSAGES[target]


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


def create_app(database_url: str | None = None) -> FastAPI:
    engine = build_engine(database_url)
    session_factory = build_session_factory(engine)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        Base.metadata.create_all(bind=engine)
        with session_factory() as session:
            ensure_demo_data(session)
            session.commit()
        yield

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.state.engine = engine
    app.state.SessionLocal = session_factory
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

    @app.middleware("http")
    async def resolve_api_user(request: Request, call_next):
        if not request.url.path.startswith("/api"):
            return await call_next(request)

        user_email = (request.headers.get("X-User-Email") or "").strip()
        if not user_email:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "X-User-Email header required"},
            )

        with session_factory() as auth_session:
            user = auth_session.scalar(user_query().where(User.email == user_email).limit(1))

        if user is None:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Unknown user"},
            )

        request.state.api_user_email = user_email
        return await call_next(request)

    @app.get("/", include_in_schema=False)
    def home(current_user: User = Depends(get_current_user)):
        return RedirectResponse(home_path_for(current_user.role), status_code=status.HTTP_303_SEE_OTHER)

    @app.get("/switch-user", include_in_schema=False)
    def switch_user(
        email: str,
        next: str = "/",
        session: Session = Depends(get_session),
    ):
        user = session.scalar(select(User).where(User.email == email).limit(1))
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown user")
        safe_next = next if next.startswith("/") else "/"
        response = RedirectResponse(safe_next, status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie("fixhub_user", email, samesite="lax")
        return response

    @app.get("/api/me")
    def api_me(current_user: User = Depends(get_current_user)):
        return serialize_user(current_user)

    @app.post("/api/jobs", status_code=status.HTTP_201_CREATED)
    def create_job(
        payload: JobCreateIn,
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user),
    ):
        require_role(current_user, UserRole.resident)
        job = Job(
            title=clean_text(payload.title, "title"),
            description=clean_text(payload.description, "description"),
            location=clean_text(payload.location, "location"),
            status=JobStatus.new,
            created_by=current_user.id,
        )
        session.add(job)
        session.flush()
        append_event(session, job=job, actor=current_user, message="Report created")
        session.commit()
        return serialize_job(visible_job(session, current_user, job.id))

    @app.get("/api/jobs")
    def list_jobs(
        mine: bool = False,
        assigned: bool = False,
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user),
    ):
        return [serialize_job(job) for job in visible_jobs(session, current_user, mine=mine, assigned=assigned)]

    @app.get("/api/jobs/{job_id}")
    def get_job(
        job_id: uuid.UUID,
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user),
    ):
        return serialize_job(visible_job(session, current_user, job_id))

    @app.patch("/api/jobs/{job_id}")
    def update_job(
        job_id: uuid.UUID,
        payload: JobPatchIn,
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
                        messages.append(STATUS_EVENT_MESSAGES[JobStatus.new])
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
                    messages.append(STATUS_EVENT_MESSAGES[JobStatus.assigned])

        if "status" in changes:
            status_message = apply_status_change(job, changes["status"], current_user)
            if status_message is not None:
                messages.append(status_message)

        for message in messages:
            append_event(session, job=job, actor=current_user, message=message)

        session.commit()
        return serialize_job(visible_job(session, current_user, job.id))

    @app.get("/api/jobs/{job_id}/events")
    def get_job_events(
        job_id: uuid.UUID,
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user),
    ):
        visible_job(session, current_user, job_id)
        return [serialize_event(event) for event in visible_events(session, job_id)]

    @app.post("/api/jobs/{job_id}/events", status_code=status.HTTP_201_CREATED)
    def add_event(
        job_id: uuid.UUID,
        payload: EventCreateIn,
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

    @app.get("/resident/report", response_class=HTMLResponse, include_in_schema=False)
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

    @app.get("/resident/jobs", response_class=HTMLResponse, include_in_schema=False)
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

    @app.get("/resident/jobs/{job_id}", response_class=HTMLResponse, include_in_schema=False)
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

    @app.get("/admin/jobs", response_class=HTMLResponse, include_in_schema=False)
    def admin_jobs_page(
        request: Request,
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user),
    ):
        require_role(current_user, UserRole.admin)
        jobs = [serialize_job(job) for job in visible_jobs(session, current_user)]
        return render_page(
            request=request,
            session=session,
            current_user=current_user,
            template_name="admin_jobs.html",
            jobs=jobs,
            counts=build_job_counts(jobs),
        )

    @app.get("/admin/jobs/{job_id}", response_class=HTMLResponse, include_in_schema=False)
    def admin_job_page(
        job_id: uuid.UUID,
        request: Request,
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user),
    ):
        require_role(current_user, UserRole.admin)
        job = visible_job(session, current_user, job_id)
        contractor_orgs = [
            {
                "id": organisation.id,
                "name": organisation.name,
            }
            for organisation in session.scalars(
                select(Organisation)
                .where(Organisation.type == OrganisationType.contractor)
                .order_by(Organisation.name.asc())
            )
        ]
        return render_page(
            request=request,
            session=session,
            current_user=current_user,
            template_name="admin_job.html",
            job=serialize_job(job),
            events=[serialize_event(event) for event in visible_events(session, job_id)],
            contractor_orgs=contractor_orgs,
        )

    @app.get("/contractor/jobs", response_class=HTMLResponse, include_in_schema=False)
    def contractor_jobs_page(
        request: Request,
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user),
    ):
        require_role(current_user, UserRole.contractor)
        jobs = [serialize_job(job) for job in visible_jobs(session, current_user, assigned=True)]
        return render_page(
            request=request,
            session=session,
            current_user=current_user,
            template_name="contractor_jobs.html",
            jobs=jobs,
        )

    @app.get("/contractor/jobs/{job_id}", response_class=HTMLResponse, include_in_schema=False)
    def contractor_job_page(
        job_id: uuid.UUID,
        request: Request,
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user),
    ):
        require_role(current_user, UserRole.contractor)
        job = visible_job(session, current_user, job_id)
        return render_page(
            request=request,
            session=session,
            current_user=current_user,
            template_name="contractor_job.html",
            job=serialize_job(job),
            events=[serialize_event(event) for event in visible_events(session, job_id)],
        )

    return app


app = create_app()
