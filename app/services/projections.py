from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.models import JobStatus


RESIDENT_RECURRENCE_REASON_CODES = {
    "issue_still_present",
    "resident_reported_recurrence",
}
RESIDENT_ACCESS_REASON_CODES = {
    "resident_access_update",
    "resident_access_issue",
}
RESPONSIBILITY_OWNER_LABELS = {
    "reception_admin": "Front desk",
    "triage_officer": "Property manager",
    "coordinator": "Dispatch coordinator",
    "contractor": "Contractor",
    "resident": "Resident",
}
SIGNAL_HEADLINES_BY_STAGE = {
    "reception": "Resident-facing update recorded without changing lifecycle state",
    "triage": "Further review recorded without changing lifecycle state",
    "coordination": "Coordination follow-up recorded without changing lifecycle state",
    "execution": "Field update recorded without changing lifecycle state",
}
SIGNAL_NEXT_STEPS_BY_STAGE = {
    "reception": "Review the latest note and decide whether intake or triage needs to change.",
    "triage": "Apply this review to the next scope, triage, or scheduling decision.",
    "coordination": "Update the booking, dispatch plan, or next handoff using this note.",
    "execution": "Record the next field outcome so operations and residents can work from the same update.",
}
ASSIGNMENT_SIGNAL_HEADLINES = {
    "set": "Dispatch target updated without changing lifecycle state",
    "cleared": "Dispatch target cleared without changing lifecycle state",
}
GENERIC_STATUS_MESSAGES = {
    JobStatus.new.value: "Returned job to intake review",
    JobStatus.assigned.value: "Dispatch target recorded",
    JobStatus.triaged.value: "Triage review recorded",
    JobStatus.scheduled.value: "Visit scheduling recorded",
    JobStatus.in_progress.value: "Contractor attendance recorded",
    JobStatus.on_hold.value: "Hold recorded",
    JobStatus.blocked.value: "Execution issue recorded",
    JobStatus.completed.value: "Completion recorded",
    JobStatus.cancelled.value: "Cancellation recorded",
    JobStatus.reopened.value: "Reopened after prior completion",
    JobStatus.follow_up_scheduled.value: "Follow-up visit recorded",
    JobStatus.escalated.value: "Escalation recorded",
}


def _event_order_key(event: Any) -> tuple[datetime, Any]:
    return (event.created_at, event.id)


def derive_job_status_from_events(events: Iterable[Any]) -> JobStatus:
    derived_status = JobStatus.new

    for event in sorted(events, key=_event_order_key):
        target_status = getattr(event, "target_status", None)
        if target_status is not None:
            derived_status = target_status

    return derived_status


def sync_job_status_from_events(job: Any) -> JobStatus:
    job.status = derive_job_status_from_events(job.events)
    return job.status


@dataclass(frozen=True)
class CoordinationSummary:
    headline: str
    owner_label: str
    detail: str | None = None
    next_step: str | None = None


@dataclass(frozen=True)
class AssignmentProjection:
    assigned_org_id: Any | None
    assigned_org_name: str | None
    assigned_contractor_user_id: Any | None
    assigned_contractor_name: str | None
    assignee_scope: str | None
    assignee_label: str | None


def latest_assignment_event(events: Iterable[Any]) -> Any | None:
    ordered_events = sorted(events, key=_event_order_key)
    for event in reversed(ordered_events):
        if getattr(event, "event_type", None) == "assignment":
            return event
    return None


def sync_job_assignment_from_events(job: Any) -> AssignmentProjection:
    assignment_event = latest_assignment_event(job.events)
    if assignment_event is None:
        return derive_assignment_projection(job, job.events)

    job.assigned_org_id = getattr(assignment_event, "assigned_org_id", None)
    job.assigned_contractor_user_id = getattr(assignment_event, "assigned_contractor_user_id", None)
    if hasattr(job, "assigned_org"):
        job.assigned_org = getattr(assignment_event, "assigned_org", None)
    if hasattr(job, "assigned_contractor"):
        job.assigned_contractor = getattr(assignment_event, "assigned_contractor", None)

    return _assignment_projection_from_snapshot(
        assigned_org_id=job.assigned_org_id,
        assigned_org_name=getattr(getattr(job, "assigned_org", None), "name", None),
        assigned_contractor_user_id=job.assigned_contractor_user_id,
        assigned_contractor_name=getattr(getattr(job, "assigned_contractor", None), "name", None),
    )


@dataclass(frozen=True)
class CoordinationProjection:
    status: JobStatus
    headline: str
    owner_label: str
    detail: str | None
    action_required_by: str | None
    action_required_summary: str | None
    responsibility_stage: str | None
    owner_scope: str | None
    responsibility_owner: str | None
    latest_event_id: Any | None
    latest_event_type: str | None
    latest_event_at: datetime | None


@dataclass(frozen=True)
class RoleUpdateProjection:
    actor_label: str
    actor_role: str
    message: str
    reason_code: str | None
    created_at: datetime


def _enum_value(value: Any) -> str | None:
    if value is None:
        return None
    return getattr(value, "value", value)


def _is_generic_status_echo(event: Any) -> bool:
    target_status = _enum_value(getattr(event, "target_status", None))
    if target_status is None:
        return False
    return getattr(event, "message", None) == GENERIC_STATUS_MESSAGES.get(target_status)


def _is_actionable_role_update(event: Any) -> bool:
    event_type = _enum_value(getattr(event, "event_type", None))
    if event_type == "report_created":
        return False
    if _is_generic_status_echo(event):
        return False
    return bool(getattr(event, "message", None))


def latest_meaningful_event(events: Iterable[Any]) -> Any | None:
    meaningful_events = [event for event in sorted(events, key=_event_order_key) if getattr(event, "event_type", None)]
    if not meaningful_events:
        return None
    return meaningful_events[-1]


def latest_coordination_signal(events: Iterable[Any]) -> Any | None:
    ordered_events = sorted(events, key=_event_order_key)
    signal_events = [
        event
        for event in ordered_events
        if (
            getattr(event, "target_status", None) is not None
            or getattr(event, "reason_code", None) is not None
            or getattr(event, "responsibility_stage", None) is not None
            or getattr(event, "owner_scope", None) is not None
            or getattr(event, "responsibility_owner", None) is not None
        )
    ]
    if not signal_events:
        return None
    return signal_events[-1]


def coordination_anchor_event(events: Iterable[Any], status: JobStatus) -> Any | None:
    latest_signal = latest_coordination_signal(events)
    if latest_signal is not None and getattr(latest_signal, "target_status", None) is None:
        return latest_signal
    return latest_event_for_status(events, status)


def latest_event_for_status(events: Iterable[Any], status: JobStatus) -> Any | None:
    ordered_events = sorted(events, key=_event_order_key)

    if status == JobStatus.assigned:
        assignment_events = [event for event in ordered_events if getattr(event, "event_type", None) == "assignment"]
        if assignment_events:
            return assignment_events[-1]

    matching_events = [event for event in ordered_events if getattr(event, "target_status", None) == status]
    if matching_events:
        return matching_events[-1]

    if status == JobStatus.new:
        report_events = [event for event in ordered_events if getattr(event, "event_type", None) == "report_created"]
        if report_events:
            return report_events[-1]

    return None


def coordination_summary(job: Any, events: Iterable[Any]) -> CoordinationSummary:
    ordered_events = sorted(events, key=_event_order_key)
    latest_event = latest_meaningful_event(events)
    status = derive_job_status_from_events(ordered_events)
    status_event = latest_event_for_status(ordered_events, status)
    anchor_event = coordination_anchor_event(ordered_events, status)
    latest_message = getattr(status_event, "message", None) or getattr(latest_event, "message", None)
    latest_reason = getattr(status_event, "reason_code", None)
    latest_event_reason = getattr(latest_event, "reason_code", None)
    latest_actor_role = getattr(getattr(latest_event, "actor_user", None), "role", None)
    latest_actor_role_value = getattr(latest_actor_role, "value", latest_actor_role)

    if latest_actor_role_value == "resident" and latest_event_reason in RESIDENT_ACCESS_REASON_CODES:
        return CoordinationSummary(
            headline="Resident sent an access update that operations need to apply",
            owner_label="Property manager",
            detail=getattr(latest_event, "message", None),
            next_step="Apply the resident's access update to the visit plan or contractor handoff.",
        )

    latest_signal_status = getattr(anchor_event, "target_status", None)
    latest_signal_stage = _enum_value(getattr(anchor_event, "responsibility_stage", None))
    latest_signal_owner = _enum_value(getattr(anchor_event, "responsibility_owner", None))
    latest_signal_message = getattr(anchor_event, "message", None)
    if (
        anchor_event is not None
        and latest_signal_status is None
        and anchor_event is not status_event
    ):
        latest_signal_type = _enum_value(getattr(anchor_event, "event_type", None))
        if latest_signal_type == "assignment":
            assignment_changed_to_clear = (
                getattr(anchor_event, "assigned_org_id", None) is None
                and getattr(anchor_event, "assigned_contractor_user_id", None) is None
            )
            return CoordinationSummary(
                headline=ASSIGNMENT_SIGNAL_HEADLINES["cleared" if assignment_changed_to_clear else "set"],
                owner_label=RESPONSIBILITY_OWNER_LABELS.get(latest_signal_owner, "Operations"),
                detail=latest_signal_message,
                next_step="Review the assignment change and record the next dispatch instruction.",
            )
        return CoordinationSummary(
            headline=SIGNAL_HEADLINES_BY_STAGE.get(latest_signal_stage, "Operational update recorded without changing lifecycle state"),
            owner_label=RESPONSIBILITY_OWNER_LABELS.get(latest_signal_owner, "Operations"),
            detail=latest_signal_message,
            next_step=SIGNAL_NEXT_STEPS_BY_STAGE.get(
                latest_signal_stage,
                "Review the latest note and record the next operational instruction.",
            ),
        )

    if status == JobStatus.new:
        return CoordinationSummary(
            headline="New report waiting for intake review",
            owner_label="Front desk",
            detail=latest_message,
            next_step="Review the report, confirm scope and location, then hand it into triage or dispatch.",
        )
    if status == JobStatus.assigned:
        return CoordinationSummary(
            headline="Dispatch target selected; triage still required",
            owner_label="Property manager",
            detail=latest_message,
            next_step="Review the assigned trade, confirm scope, and decide whether the job is ready to schedule.",
        )
    if status == JobStatus.triaged:
        return CoordinationSummary(
            headline="Scope reviewed; attendance still needs scheduling",
            owner_label="Property manager",
            detail=latest_message,
            next_step="Book an attendance window with the resident and contractor, then record the planned visit.",
        )
    if status == JobStatus.scheduled:
        return CoordinationSummary(
            headline="Visit scheduled; waiting for contractor attendance",
            owner_label="Contractor",
            detail=latest_message,
            next_step="Attend the booked window and record whether work started, was blocked, or was completed.",
        )
    if status == JobStatus.in_progress:
        return CoordinationSummary(
            headline="Work in progress on site",
            owner_label="Contractor",
            detail=latest_message,
            next_step="Post what changed on site so operations and the resident can see the current field position.",
        )
    if status == JobStatus.blocked:
        detail = latest_reason or latest_message
        return CoordinationSummary(
            headline="Work blocked and needs coordination",
            owner_label="Dispatch coordinator",
            detail=detail,
            next_step="Resolve the blocker, then either reschedule, hold, or escalate the job.",
        )
    if status == JobStatus.on_hold:
        detail = latest_reason or latest_message
        return CoordinationSummary(
            headline="Job on hold pending further action",
            owner_label="Property manager",
            detail=detail,
            next_step="Record the condition needed to bring the job back into triage or scheduling.",
        )
    if status == JobStatus.completed:
        if latest_actor_role_value == "resident" and latest_event_reason in RESIDENT_RECURRENCE_REASON_CODES:
            return CoordinationSummary(
                headline="Resident says the issue is still active after completion",
                owner_label="Property manager",
                detail=getattr(latest_event, "message", None),
                next_step="Review the recurrence report and decide whether to reopen or schedule follow-up.",
            )
        return CoordinationSummary(
            headline="Work marked complete",
            owner_label="Resident",
            detail=latest_message or "Resident confirmation or recurrence report is the next signal.",
            next_step="Confirm the issue is resolved or report if it recurs after the visit.",
        )
    if status == JobStatus.reopened:
        detail = latest_reason or latest_message
        return CoordinationSummary(
            headline="Issue reopened after prior completion",
            owner_label="Property manager",
            detail=detail,
            next_step="Review the reopened issue and decide whether to reschedule or re-triage.",
        )
    if status == JobStatus.follow_up_scheduled:
        detail = latest_reason or latest_message
        return CoordinationSummary(
            headline="Return visit scheduled after recurrence",
            owner_label="Contractor",
            detail=detail,
            next_step="Attend the return visit and record the outcome from site.",
        )
    if status == JobStatus.escalated:
        detail = latest_reason or latest_message
        return CoordinationSummary(
            headline="Escalated for operational review",
            owner_label="Dispatch coordinator",
            detail=detail,
            next_step="Decide the coordination path and record the next operational instruction.",
        )
    if status == JobStatus.cancelled:
        detail = latest_reason or latest_message
        return CoordinationSummary(
            headline="Job cancelled",
            owner_label="Operations",
            detail=detail,
            next_step="Keep the cancellation reason in the record for future reference.",
        )
    return CoordinationSummary(
        headline="Job updated",
        owner_label="Operations",
        detail=latest_message,
        next_step="Review the latest event and record the next operational instruction.",
    )


def _assignment_projection_from_snapshot(
    *,
    assigned_org_id: Any | None,
    assigned_org_name: str | None,
    assigned_contractor_user_id: Any | None,
    assigned_contractor_name: str | None,
) -> AssignmentProjection:
    assignee_scope = None
    assignee_label = None
    if assigned_contractor_user_id is not None:
        assignee_scope = "user"
        assignee_label = assigned_contractor_name
    elif assigned_org_id is not None:
        assignee_scope = "organisation"
        assignee_label = assigned_org_name

    return AssignmentProjection(
        assigned_org_id=assigned_org_id,
        assigned_org_name=assigned_org_name,
        assigned_contractor_user_id=assigned_contractor_user_id,
        assigned_contractor_name=assigned_contractor_name,
        assignee_scope=assignee_scope,
        assignee_label=assignee_label,
    )


def derive_assignment_projection(job: Any, events: Iterable[Any]) -> AssignmentProjection:
    ordered_events = sorted(events, key=_event_order_key)

    for event in reversed(ordered_events):
        if getattr(event, "event_type", None) != "assignment":
            continue

        assigned_org = getattr(event, "assigned_org", None)
        assigned_contractor = getattr(event, "assigned_contractor", None)
        return _assignment_projection_from_snapshot(
            assigned_org_id=getattr(event, "assigned_org_id", None),
            assigned_org_name=getattr(assigned_org, "name", None),
            assigned_contractor_user_id=getattr(event, "assigned_contractor_user_id", None),
            assigned_contractor_name=getattr(assigned_contractor, "name", None),
        )

    assigned_org = getattr(job, "assigned_org", None)
    assigned_contractor = getattr(job, "assigned_contractor", None)
    return _assignment_projection_from_snapshot(
        assigned_org_id=getattr(job, "assigned_org_id", None),
        assigned_org_name=getattr(assigned_org, "name", None),
        assigned_contractor_user_id=getattr(job, "assigned_contractor_user_id", None),
        assigned_contractor_name=getattr(assigned_contractor, "name", None),
    )


def latest_role_update(events: Iterable[Any], *, roles: set[str]) -> RoleUpdateProjection | None:
    ordered_events = sorted(events, key=_event_order_key)
    for event in reversed(ordered_events):
        actor_user = getattr(event, "actor_user", None)
        actor_role = getattr(actor_user, "role", None)
        actor_role_value = getattr(actor_role, "value", actor_role)
        if actor_role_value not in roles:
            continue
        if not _is_actionable_role_update(event):
            continue
        actor_name = getattr(actor_user, "name", None) or "System"
        organisation = getattr(actor_user, "organisation", None)
        organisation_name = getattr(organisation, "name", None)
        if organisation_name:
            actor_label = f"{actor_name} ({organisation_name})"
        else:
            actor_label = actor_name
        return RoleUpdateProjection(
            actor_label=actor_label,
            actor_role=actor_role_value,
            message=getattr(event, "message", None) or "",
            reason_code=getattr(event, "reason_code", None),
            created_at=getattr(event, "created_at"),
        )
    return None


@dataclass(frozen=True)
class PendingSignalProjection:
    headline: str
    summary: str
    actor_label: str
    actor_role: str
    created_at: datetime


def _newer_role_update(
    baseline: RoleUpdateProjection | None,
    candidates: Iterable[RoleUpdateProjection | None],
) -> RoleUpdateProjection | None:
    comparable = [candidate for candidate in candidates if candidate is not None]
    if baseline is not None:
        comparable = [candidate for candidate in comparable if candidate.created_at > baseline.created_at]
    if not comparable:
        return None
    comparable.sort(key=lambda candidate: candidate.created_at)
    return comparable[-1]


def _pending_signal_copy(
    *,
    owner_role: str | None,
    status: JobStatus,
    source: RoleUpdateProjection,
) -> tuple[str, str]:
    if source.actor_role == "resident":
        if source.reason_code in RESIDENT_ACCESS_REASON_CODES:
            if owner_role == "contractor":
                return (
                    "Resident access detail changed after the last field update",
                    "Read the resident note before attending or recording further field progress.",
                )
            return (
                "Resident access detail needs operations follow-through",
                "Apply the resident note to scheduling, dispatch, or follow-up before the next visit.",
            )
        if source.reason_code in RESIDENT_RECURRENCE_REASON_CODES:
            return (
                "Resident reported the issue is still active",
                "Review the recurrence and decide whether to reopen the job or schedule follow-up work.",
            )
        return (
            "Resident added a newer coordination note",
            "Use the resident update before the next workflow change or callback.",
        )

    if source.actor_role == "contractor":
        if status == JobStatus.blocked:
            return (
                "Field blocker needs coordination",
                "Review the field update and record the rebooking, access, or escalation path.",
            )
        if status == JobStatus.completed and owner_role == "resident":
            return (
                "Field team marked the work complete",
                "Confirm whether the issue is resolved or report if it returns after the visit.",
            )
        return (
            "Field progress is newer than the last operations update",
            "Use the site update before the next triage, dispatch, or resident handoff.",
        )

    if source.actor_role in {"admin", "reception_admin", "triage_officer", "coordinator"}:
        if owner_role == "contractor":
            return (
                "New operations handoff is waiting on contractor action",
                "Check the latest booking or scope note before attending site or posting progress.",
            )
        if owner_role == "resident":
            if status == JobStatus.completed:
                return (
                    "Completion update is waiting on resident confirmation",
                    "Confirm whether the issue is resolved after the visit or report recurrence.",
                )
            return (
                "Staff posted a newer update for the resident",
                "Read the latest staff note before replying or following up.",
            )
        return (
            "Operations posted a newer coordination update",
            "Use the latest staff handoff before the next workflow change.",
        )

    return (
        "A newer coordination signal needs attention",
        "Review the latest update before recording the next action on this job.",
    )


def derive_pending_signal(job: Any, events: Iterable[Any]) -> PendingSignalProjection | None:
    ordered_events = sorted(events, key=_event_order_key)
    if not ordered_events:
        return None

    projection = derive_coordination_projection(job, ordered_events)
    owner_role = projection.responsibility_owner
    status = projection.status
    latest_resident = latest_role_update(ordered_events, roles={"resident"})
    latest_operations = latest_role_update(
        ordered_events,
        roles={"admin", "reception_admin", "triage_officer", "coordinator"},
    )
    latest_contractor = latest_role_update(ordered_events, roles={"contractor"})

    source: RoleUpdateProjection | None = None
    if owner_role in {"reception_admin", "triage_officer", "coordinator"}:
        source = _newer_role_update(latest_operations, [latest_resident, latest_contractor])
    elif owner_role == "contractor":
        source = _newer_role_update(latest_contractor, [latest_resident, latest_operations])
    elif owner_role == "resident":
        source = _newer_role_update(latest_resident, [latest_operations, latest_contractor])

    if source is None:
        return None

    headline, summary = _pending_signal_copy(owner_role=owner_role, status=status, source=source)
    return PendingSignalProjection(
        headline=headline,
        summary=summary,
        actor_label=source.actor_label,
        actor_role=source.actor_role,
        created_at=source.created_at,
    )


def derive_coordination_projection(job: Any, events: Iterable[Any]) -> CoordinationProjection:
    ordered_events = sorted(events, key=_event_order_key)
    latest_event = ordered_events[-1] if ordered_events else None
    status = derive_job_status_from_events(ordered_events)
    summary = coordination_summary(job, ordered_events)
    assignment = derive_assignment_projection(job, ordered_events)
    anchor_event = coordination_anchor_event(ordered_events, status)
    responsibility_stage = _enum_value(getattr(anchor_event, "responsibility_stage", None))
    owner_scope = _enum_value(getattr(anchor_event, "owner_scope", None))
    responsibility_owner = _enum_value(getattr(anchor_event, "responsibility_owner", None))

    owner_label = summary.owner_label
    if status in {JobStatus.scheduled, JobStatus.in_progress, JobStatus.follow_up_scheduled} and assignment.assignee_label:
        owner_label = assignment.assignee_label

    return CoordinationProjection(
        status=status,
        headline=summary.headline,
        owner_label=owner_label,
        detail=summary.detail,
        action_required_by=owner_label,
        action_required_summary=summary.next_step,
        responsibility_stage=responsibility_stage,
        owner_scope=owner_scope,
        responsibility_owner=responsibility_owner,
        latest_event_id=getattr(latest_event, "id", None),
        latest_event_type=_enum_value(getattr(latest_event, "event_type", None)),
        latest_event_at=getattr(latest_event, "created_at", None),
    )
