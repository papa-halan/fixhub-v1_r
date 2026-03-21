from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import (
    Event,
    EventType,
    Job,
    JobStatus,
    OwnerScope,
    ResponsibilityOwner,
    ResponsibilityStage,
    User,
    UserRole,
)


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
OPERATIONS_ROLES = (
    UserRole.admin,
    UserRole.reception_admin,
    UserRole.triage_officer,
    UserRole.coordinator,
)
ASSIGNMENT_ROLES = (UserRole.admin, UserRole.coordinator)
TRIAGE_ROLES = (UserRole.admin, UserRole.triage_officer)
COORDINATION_ROLES = (UserRole.admin, UserRole.coordinator)
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


def role_label(role: UserRole | str | None) -> str | None:
    if role is None:
        return None
    role_value = role.value if isinstance(role, UserRole) else role
    return role_value.replace("_", " ").title()


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

    if target == JobStatus.completed and reason_code is None and responsibility_stage is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="reason_code or responsibility_stage is required when moving a job to completed",
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
