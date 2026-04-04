from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    resident = "resident"
    admin = "admin"
    reception_admin = "reception_admin"
    triage_officer = "triage_officer"
    coordinator = "coordinator"
    contractor = "contractor"


class OrganisationType(str, Enum):
    university = "university"
    contractor = "contractor"


class ContractorMode(str, Enum):
    maintenance_team = "maintenance_team"
    external_contractor = "external_contractor"


class LocationType(str, Enum):
    site = "site"
    building = "building"
    space = "space"
    unit = "unit"


class JobStatus(str, Enum):
    new = "new"
    assigned = "assigned"
    triaged = "triaged"
    scheduled = "scheduled"
    in_progress = "in_progress"
    on_hold = "on_hold"
    blocked = "blocked"
    completed = "completed"
    cancelled = "cancelled"
    reopened = "reopened"
    follow_up_scheduled = "follow_up_scheduled"
    escalated = "escalated"


class EventType(str, Enum):
    report_created = "report_created"
    note = "note"
    assignment = "assignment"
    status_change = "status_change"
    schedule = "schedule"
    escalation = "escalation"
    completion = "completion"
    follow_up = "follow_up"


class ResponsibilityStage(str, Enum):
    reception = "reception"
    triage = "triage"
    coordination = "coordination"
    execution = "execution"


class OwnerScope(str, Enum):
    organisation = "organisation"
    user = "user"


class ResponsibilityOwner(str, Enum):
    reception_admin = "reception_admin"
    triage_officer = "triage_officer"
    coordinator = "coordinator"
    contractor = "contractor"
    resident = "resident"


class ResidentUpdateReason(str, Enum):
    resident_access_update = "resident_access_update"
    resident_access_issue = "resident_access_issue"
    issue_still_present = "issue_still_present"
    resident_reported_recurrence = "resident_reported_recurrence"
    resident_confirmed_resolved = "resident_confirmed_resolved"


class ReportChannel(str, Enum):
    resident_portal = "resident_portal"
    staff_created = "staff_created"
    security_after_hours = "security_after_hours"
    inspection_housekeeping = "inspection_housekeeping"
