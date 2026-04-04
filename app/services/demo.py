from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Asset,
    ContractorMode,
    EventType,
    Job,
    JobStatus,
    Location,
    LocationType,
    OwnerScope,
    Organisation,
    OrganisationType,
    ReportChannel,
    ResponsibilityStage,
    User,
    UserRole,
)
from app.services.catalog import location_label
from app.services.passwords import hash_password, verify_password
from app.services.projections import sync_job_status_from_events
from app.services.workflow import append_event


@dataclass(frozen=True)
class DemoOrganisation:
    name: str
    type: OrganisationType
    parent_name: str | None = None
    contractor_mode: ContractorMode | None = None


@dataclass(frozen=True)
class DemoUser:
    name: str
    email: str
    role: UserRole
    organisation_name: str | None = None


@dataclass(frozen=True)
class DemoLocation:
    name: str
    organisation_name: str
    type: LocationType
    parent_name: str | None = None


@dataclass(frozen=True)
class DemoAsset:
    location_name: str
    name: str


@dataclass(frozen=True)
class DemoJobEvent:
    actor_email: str
    message: str
    event_type: EventType = EventType.note
    target_status: JobStatus | None = None
    reason_code: str | None = None
    responsibility_stage: ResponsibilityStage | None = None
    owner_scope: OwnerScope | None = None
    assigned_org_name: str | None = None
    assigned_contractor_email: str | None = None


@dataclass(frozen=True)
class DemoJob:
    title: str
    description: str
    creator_email: str
    location_name: str
    intake_channel: ReportChannel = ReportChannel.resident_portal
    asset_name: str | None = None
    location_detail_text: str | None = None
    events: tuple[DemoJobEvent, ...] = ()


DEMO_ORGANISATIONS: tuple[DemoOrganisation, ...] = (
    DemoOrganisation(
        name="University of Newcastle",
        type=OrganisationType.university,
    ),
    DemoOrganisation(
        name="Student Living",
        type=OrganisationType.university,
        parent_name="University of Newcastle",
    ),
    DemoOrganisation(
        name="Newcastle Plumbing",
        type=OrganisationType.contractor,
        contractor_mode=ContractorMode.external_contractor,
    ),
    DemoOrganisation(
        name="Campus Maintenance",
        type=OrganisationType.contractor,
        contractor_mode=ContractorMode.maintenance_team,
    ),
    DemoOrganisation(
        name="Independent Contractors",
        type=OrganisationType.contractor,
        contractor_mode=ContractorMode.external_contractor,
    ),
)


DEMO_USERS: tuple[DemoUser, ...] = (
    DemoUser(
        name="Riley Resident",
        email="resident@fixhub.test",
        role=UserRole.resident,
        organisation_name="Student Living",
    ),
    DemoUser(
        name="Avery Resident",
        email="resident.blockb@fixhub.test",
        role=UserRole.resident,
        organisation_name="Student Living",
    ),
    DemoUser(
        name="Morgan Resident",
        email="resident.common@fixhub.test",
        role=UserRole.resident,
        organisation_name="Student Living",
    ),
    DemoUser(
        name="Sky System Admin",
        email="admin@fixhub.test",
        role=UserRole.admin,
        organisation_name="Student Living",
    ),
    DemoUser(
        name="Fran Front Desk",
        email="reception@fixhub.test",
        role=UserRole.reception_admin,
        organisation_name="Student Living",
    ),
    DemoUser(
        name="Priya Property Manager",
        email="triage@fixhub.test",
        role=UserRole.triage_officer,
        organisation_name="Student Living",
    ),
    DemoUser(
        name="Casey Dispatch Coordinator",
        email="coordinator@fixhub.test",
        role=UserRole.coordinator,
        organisation_name="Student Living",
    ),
    DemoUser(
        name="Devon Contractor",
        email="contractor@fixhub.test",
        role=UserRole.contractor,
        organisation_name="Newcastle Plumbing",
    ),
    DemoUser(
        name="Maddie Maintenance Technician",
        email="maintenance.contractor@fixhub.test",
        role=UserRole.contractor,
        organisation_name="Campus Maintenance",
    ),
    DemoUser(
        name="Indy Independent Contractor",
        email="independent.contractor@fixhub.test",
        role=UserRole.contractor,
        organisation_name="Independent Contractors",
    ),
)


DEMO_LOCATIONS: tuple[DemoLocation, ...] = (
    DemoLocation(
        name="Callaghan Campus",
        organisation_name="Student Living",
        type=LocationType.site,
    ),
    DemoLocation(
        name="Block A",
        organisation_name="Student Living",
        type=LocationType.building,
        parent_name="Callaghan Campus",
    ),
    DemoLocation(
        name="Block B",
        organisation_name="Student Living",
        type=LocationType.building,
        parent_name="Callaghan Campus",
    ),
    DemoLocation(
        name="Block C",
        organisation_name="Student Living",
        type=LocationType.building,
        parent_name="Callaghan Campus",
    ),
    DemoLocation(
        name="Block D",
        organisation_name="Student Living",
        type=LocationType.building,
        parent_name="Callaghan Campus",
    ),
    DemoLocation(
        name="Block E",
        organisation_name="Student Living",
        type=LocationType.building,
        parent_name="Callaghan Campus",
    ),
    DemoLocation(
        name="Block F",
        organisation_name="Student Living",
        type=LocationType.building,
        parent_name="Callaghan Campus",
    ),
    DemoLocation(
        name="Block G",
        organisation_name="Student Living",
        type=LocationType.building,
        parent_name="Callaghan Campus",
    ),
    DemoLocation(
        name="Block H",
        organisation_name="Student Living",
        type=LocationType.building,
        parent_name="Callaghan Campus",
    ),
    DemoLocation(
        name="Block J",
        organisation_name="Student Living",
        type=LocationType.building,
        parent_name="Callaghan Campus",
    ),
    DemoLocation(
        name="Block K",
        organisation_name="Student Living",
        type=LocationType.building,
        parent_name="Callaghan Campus",
    ),
    DemoLocation(
        name="Block L",
        organisation_name="Student Living",
        type=LocationType.building,
        parent_name="Callaghan Campus",
    ),
    DemoLocation(
        name="Block A Room 14",
        organisation_name="Student Living",
        type=LocationType.unit,
        parent_name="Block A",
    ),
    DemoLocation(
        name="Block B Room 8",
        organisation_name="Student Living",
        type=LocationType.unit,
        parent_name="Block B",
    ),
    DemoLocation(
        name="Block A Common Room",
        organisation_name="Student Living",
        type=LocationType.space,
        parent_name="Block A",
    ),
    DemoLocation(
        name="Block B Laundry",
        organisation_name="Student Living",
        type=LocationType.space,
        parent_name="Block B",
    ),
    DemoLocation(
        name="Block C Room 5",
        organisation_name="Student Living",
        type=LocationType.unit,
        parent_name="Block C",
    ),
    DemoLocation(
        name="Block D Room 12",
        organisation_name="Student Living",
        type=LocationType.unit,
        parent_name="Block D",
    ),
    DemoLocation(
        name="Block E Kitchen",
        organisation_name="Student Living",
        type=LocationType.space,
        parent_name="Block E",
    ),
    DemoLocation(
        name="Block F Room 3",
        organisation_name="Student Living",
        type=LocationType.unit,
        parent_name="Block F",
    ),
    DemoLocation(
        name="Block G Room 9",
        organisation_name="Student Living",
        type=LocationType.unit,
        parent_name="Block G",
    ),
    DemoLocation(
        name="Block H Room 2",
        organisation_name="Student Living",
        type=LocationType.unit,
        parent_name="Block H",
    ),
    DemoLocation(
        name="Block J Lounge",
        organisation_name="Student Living",
        type=LocationType.space,
        parent_name="Block J",
    ),
    DemoLocation(
        name="Block K Laundry",
        organisation_name="Student Living",
        type=LocationType.space,
        parent_name="Block K",
    ),
    DemoLocation(
        name="Block L Room 7",
        organisation_name="Student Living",
        type=LocationType.unit,
        parent_name="Block L",
    ),
)


DEMO_ASSETS: tuple[DemoAsset, ...] = (
    DemoAsset(location_name="Block A Room 14", name="Sink"),
    DemoAsset(location_name="Block A Room 14", name="Tap"),
    DemoAsset(location_name="Block A Room 14", name="Wardrobe Hinge"),
    DemoAsset(location_name="Block B Room 8", name="Door Closer"),
    DemoAsset(location_name="Block B Room 8", name="Bathroom Fan"),
    DemoAsset(location_name="Block A Common Room", name="Heater"),
    DemoAsset(location_name="Block B Laundry", name="Pump"),
)


DEMO_USER_EMAILS = {demo.email for demo in DEMO_USERS}

DEMO_JOBS: tuple[DemoJob, ...] = (
    DemoJob(
        title="Shower mixer leak after first repair",
        description="The Block A Room 14 shower mixer leaked around the trim after an earlier washer replacement and needed a return visit.",
        creator_email="resident@fixhub.test",
        location_name="Block A Room 14",
        asset_name="Tap",
        location_detail_text="Ensuite shower wall closest to the vanity",
        events=(
            DemoJobEvent(
                actor_email="coordinator@fixhub.test",
                message="Assigned Maddie Maintenance Technician",
                event_type=EventType.assignment,
                responsibility_stage=ResponsibilityStage.triage,
                owner_scope=OwnerScope.user,
                assigned_org_name="Campus Maintenance",
                assigned_contractor_email="maintenance.contractor@fixhub.test",
            ),
            DemoJobEvent(
                actor_email="coordinator@fixhub.test",
                message="Dispatch target selected; job moved to assigned",
                event_type=EventType.status_change,
                target_status=JobStatus.assigned,
                responsibility_stage=ResponsibilityStage.triage,
                owner_scope=OwnerScope.user,
                assigned_org_name="Campus Maintenance",
                assigned_contractor_email="maintenance.contractor@fixhub.test",
            ),
            DemoJobEvent(
                actor_email="triage@fixhub.test",
                message="Reviewed the repeat leak and confirmed a return visit was needed.",
                event_type=EventType.status_change,
                target_status=JobStatus.triaged,
                responsibility_stage=ResponsibilityStage.triage,
                owner_scope=OwnerScope.user,
            ),
            DemoJobEvent(
                actor_email="triage@fixhub.test",
                message="Booked maintenance for an afternoon access window confirmed by the resident.",
                event_type=EventType.schedule,
                target_status=JobStatus.scheduled,
                responsibility_stage=ResponsibilityStage.coordination,
                owner_scope=OwnerScope.user,
            ),
            DemoJobEvent(
                actor_email="maintenance.contractor@fixhub.test",
                message="Replaced the shower cartridge, resealed the trim, and pressure-tested the mixer.",
                event_type=EventType.completion,
                target_status=JobStatus.completed,
                responsibility_stage=ResponsibilityStage.execution,
                owner_scope=OwnerScope.user,
            ),
            DemoJobEvent(
                actor_email="resident@fixhub.test",
                message="The shower stayed dry for the rest of the week after the return visit.",
                reason_code="resident_confirmed_resolved",
                responsibility_stage=ResponsibilityStage.execution,
                owner_scope=OwnerScope.user,
            ),
        ),
    ),
    DemoJob(
        title="Shower mixer leaking again",
        description="Water is tracking under the shower mixer again after the last repair, and the resident can only provide access after classes.",
        creator_email="resident@fixhub.test",
        location_name="Block A Room 14",
        asset_name="Tap",
        location_detail_text="Ensuite shower wall closest to the vanity",
        events=(
            DemoJobEvent(
                actor_email="resident@fixhub.test",
                message="I can give access after 3pm Tuesday and the room is occupied before then.",
                reason_code="resident_access_update",
                responsibility_stage=ResponsibilityStage.coordination,
                owner_scope=OwnerScope.user,
            ),
            DemoJobEvent(
                actor_email="coordinator@fixhub.test",
                message="Assigned Maddie Maintenance Technician",
                event_type=EventType.assignment,
                responsibility_stage=ResponsibilityStage.triage,
                owner_scope=OwnerScope.user,
                assigned_org_name="Campus Maintenance",
                assigned_contractor_email="maintenance.contractor@fixhub.test",
            ),
            DemoJobEvent(
                actor_email="coordinator@fixhub.test",
                message="Dispatch target selected; job moved to assigned",
                event_type=EventType.status_change,
                target_status=JobStatus.assigned,
                responsibility_stage=ResponsibilityStage.triage,
                owner_scope=OwnerScope.user,
                assigned_org_name="Campus Maintenance",
                assigned_contractor_email="maintenance.contractor@fixhub.test",
            ),
            DemoJobEvent(
                actor_email="triage@fixhub.test",
                message="Reviewed prior repair history and confirmed campus maintenance should revisit the mixer.",
                event_type=EventType.status_change,
                target_status=JobStatus.triaged,
                responsibility_stage=ResponsibilityStage.triage,
                owner_scope=OwnerScope.user,
            ),
            DemoJobEvent(
                actor_email="triage@fixhub.test",
                message="Booked Maddie for Tuesday 15:00-17:00 after the resident access window.",
                event_type=EventType.schedule,
                target_status=JobStatus.scheduled,
                responsibility_stage=ResponsibilityStage.coordination,
                owner_scope=OwnerScope.user,
            ),
        ),
    ),
    DemoJob(
        title="Laundry pump stopped mid-cycle last week",
        description="The Block B laundry pump stopped during several wash cycles last week and required a prior plumber attendance before the current breakdown.",
        creator_email="resident.blockb@fixhub.test",
        location_name="Block B Laundry",
        intake_channel=ReportChannel.staff_created,
        asset_name="Pump",
        location_detail_text="Rear wall machine bank closest to the floor drain",
        events=(
            DemoJobEvent(
                actor_email="coordinator@fixhub.test",
                message="Assigned Newcastle Plumbing",
                event_type=EventType.assignment,
                responsibility_stage=ResponsibilityStage.triage,
                owner_scope=OwnerScope.organisation,
                assigned_org_name="Newcastle Plumbing",
            ),
            DemoJobEvent(
                actor_email="coordinator@fixhub.test",
                message="Dispatch target selected; job moved to assigned",
                event_type=EventType.status_change,
                target_status=JobStatus.assigned,
                responsibility_stage=ResponsibilityStage.triage,
                owner_scope=OwnerScope.organisation,
                assigned_org_name="Newcastle Plumbing",
            ),
            DemoJobEvent(
                actor_email="triage@fixhub.test",
                message="Confirmed plumber attendance for repeated pump stoppages in the laundry.",
                event_type=EventType.status_change,
                target_status=JobStatus.triaged,
                responsibility_stage=ResponsibilityStage.triage,
                owner_scope=OwnerScope.organisation,
            ),
            DemoJobEvent(
                actor_email="triage@fixhub.test",
                message="Booked plumber after site staff confirmed plant room access.",
                event_type=EventType.schedule,
                target_status=JobStatus.scheduled,
                responsibility_stage=ResponsibilityStage.coordination,
                owner_scope=OwnerScope.organisation,
            ),
            DemoJobEvent(
                actor_email="contractor@fixhub.test",
                message="Cleared the jammed float switch, tested multiple cycles, and restored normal drainage.",
                event_type=EventType.completion,
                target_status=JobStatus.completed,
                responsibility_stage=ResponsibilityStage.execution,
                owner_scope=OwnerScope.organisation,
            ),
        ),
    ),
    DemoJob(
        title="Laundry pump failing again",
        description="The Block B laundry pump is stopping mid-cycle again, leaving water in the machines and creating repeat resident complaints.",
        creator_email="resident.blockb@fixhub.test",
        location_name="Block B Laundry",
        asset_name="Pump",
        location_detail_text="Rear wall machine bank closest to the floor drain",
        events=(
            DemoJobEvent(
                actor_email="reception@fixhub.test",
                message="Confirmed repeated laundry complaints from Block B residents this week.",
                reason_code="repeat_resident_reports",
                responsibility_stage=ResponsibilityStage.reception,
                owner_scope=OwnerScope.organisation,
            ),
            DemoJobEvent(
                actor_email="coordinator@fixhub.test",
                message="Assigned Newcastle Plumbing",
                event_type=EventType.assignment,
                responsibility_stage=ResponsibilityStage.triage,
                owner_scope=OwnerScope.organisation,
                assigned_org_name="Newcastle Plumbing",
            ),
            DemoJobEvent(
                actor_email="coordinator@fixhub.test",
                message="Dispatch target selected; job moved to assigned",
                event_type=EventType.status_change,
                target_status=JobStatus.assigned,
                responsibility_stage=ResponsibilityStage.triage,
                owner_scope=OwnerScope.organisation,
                assigned_org_name="Newcastle Plumbing",
            ),
            DemoJobEvent(
                actor_email="triage@fixhub.test",
                message="Reviewed the repeated pump stoppage and confirmed plumber attendance is required.",
                event_type=EventType.status_change,
                target_status=JobStatus.triaged,
                responsibility_stage=ResponsibilityStage.triage,
                owner_scope=OwnerScope.organisation,
            ),
            DemoJobEvent(
                actor_email="triage@fixhub.test",
                message="Booked plumber for Wednesday morning pending plant room key handoff from site staff.",
                event_type=EventType.schedule,
                target_status=JobStatus.scheduled,
                responsibility_stage=ResponsibilityStage.coordination,
                owner_scope=OwnerScope.organisation,
            ),
            DemoJobEvent(
                actor_email="contractor@fixhub.test",
                message="Arrived on site but the plant room was locked and no key handoff was arranged.",
                event_type=EventType.status_change,
                target_status=JobStatus.blocked,
                reason_code="no_access",
                responsibility_stage=ResponsibilityStage.execution,
                owner_scope=OwnerScope.organisation,
            ),
            DemoJobEvent(
                actor_email="coordinator@fixhub.test",
                message="Need site staff to confirm key collection and a new attendance window before rebooking.",
                event_type=EventType.status_change,
                target_status=JobStatus.on_hold,
                reason_code="awaiting_access_arrangement",
                responsibility_stage=ResponsibilityStage.coordination,
                owner_scope=OwnerScope.organisation,
            ),
        ),
    ),
    DemoJob(
        title="Common room heater reset after earlier trip",
        description="The Block A common room heater had already needed one earlier reset before the latest overnight trip was reported.",
        creator_email="resident.common@fixhub.test",
        location_name="Block A Common Room",
        intake_channel=ReportChannel.inspection_housekeeping,
        asset_name="Heater",
        location_detail_text="North wall heater beside the noticeboard",
        events=(
            DemoJobEvent(
                actor_email="coordinator@fixhub.test",
                message="Assigned Campus Maintenance",
                event_type=EventType.assignment,
                responsibility_stage=ResponsibilityStage.triage,
                owner_scope=OwnerScope.organisation,
                assigned_org_name="Campus Maintenance",
            ),
            DemoJobEvent(
                actor_email="coordinator@fixhub.test",
                message="Dispatch target selected; job moved to assigned",
                event_type=EventType.status_change,
                target_status=JobStatus.assigned,
                responsibility_stage=ResponsibilityStage.triage,
                owner_scope=OwnerScope.organisation,
                assigned_org_name="Campus Maintenance",
            ),
            DemoJobEvent(
                actor_email="triage@fixhub.test",
                message="Recorded an earlier overnight heater trip and sent campus maintenance to inspect.",
                event_type=EventType.status_change,
                target_status=JobStatus.triaged,
                responsibility_stage=ResponsibilityStage.triage,
                owner_scope=OwnerScope.organisation,
            ),
            DemoJobEvent(
                actor_email="triage@fixhub.test",
                message="Booked an evening heater check while the common room was quiet.",
                event_type=EventType.schedule,
                target_status=JobStatus.scheduled,
                responsibility_stage=ResponsibilityStage.coordination,
                owner_scope=OwnerScope.organisation,
            ),
            DemoJobEvent(
                actor_email="maintenance.contractor@fixhub.test",
                message="Reset the heater, tightened the loose terminal cover, and confirmed heat output on departure.",
                event_type=EventType.completion,
                target_status=JobStatus.completed,
                responsibility_stage=ResponsibilityStage.execution,
                owner_scope=OwnerScope.organisation,
            ),
        ),
    ),
    DemoJob(
        title="Common room heater tripping overnight",
        description="The Block A common room heater is dropping out overnight again after a prior visit, so residents wake up to a cold room.",
        creator_email="resident.common@fixhub.test",
        location_name="Block A Common Room",
        asset_name="Heater",
        location_detail_text="North wall heater beside the noticeboard",
        events=(
            DemoJobEvent(
                actor_email="coordinator@fixhub.test",
                message="Assigned Maddie Maintenance Technician",
                event_type=EventType.assignment,
                responsibility_stage=ResponsibilityStage.triage,
                owner_scope=OwnerScope.user,
                assigned_org_name="Campus Maintenance",
                assigned_contractor_email="maintenance.contractor@fixhub.test",
            ),
            DemoJobEvent(
                actor_email="coordinator@fixhub.test",
                message="Dispatch target selected; job moved to assigned",
                event_type=EventType.status_change,
                target_status=JobStatus.assigned,
                responsibility_stage=ResponsibilityStage.triage,
                owner_scope=OwnerScope.user,
                assigned_org_name="Campus Maintenance",
                assigned_contractor_email="maintenance.contractor@fixhub.test",
            ),
            DemoJobEvent(
                actor_email="triage@fixhub.test",
                message="Confirmed this is a repeat heater trip after a prior reset and scheduled a return visit.",
                event_type=EventType.status_change,
                target_status=JobStatus.triaged,
                responsibility_stage=ResponsibilityStage.triage,
                owner_scope=OwnerScope.user,
            ),
            DemoJobEvent(
                actor_email="triage@fixhub.test",
                message="Booked Maddie for an early evening heater check while the common room is quiet.",
                event_type=EventType.schedule,
                target_status=JobStatus.scheduled,
                responsibility_stage=ResponsibilityStage.coordination,
                owner_scope=OwnerScope.user,
            ),
            DemoJobEvent(
                actor_email="maintenance.contractor@fixhub.test",
                message="Reset the heater, confirmed heat output, and left it running for the evening.",
                event_type=EventType.status_change,
                target_status=JobStatus.completed,
                responsibility_stage=ResponsibilityStage.execution,
                owner_scope=OwnerScope.user,
            ),
            DemoJobEvent(
                actor_email="resident.common@fixhub.test",
                message="The heater tripped again after last night's run and the room was cold this morning.",
                reason_code="issue_still_present",
                responsibility_stage=ResponsibilityStage.triage,
                owner_scope=OwnerScope.user,
            ),
        ),
    ),
    DemoJob(
        title="Bathroom fan rattling after reset",
        description="The bathroom fan in Block B Room 8 kept rattling after an earlier reset, but this latest attendance appears to have resolved it.",
        creator_email="resident.blockb@fixhub.test",
        location_name="Block B Room 8",
        intake_channel=ReportChannel.security_after_hours,
        asset_name="Bathroom Fan",
        location_detail_text="Ceiling fan above the shower",
        events=(
            DemoJobEvent(
                actor_email="coordinator@fixhub.test",
                message="Assigned Campus Maintenance",
                event_type=EventType.assignment,
                responsibility_stage=ResponsibilityStage.triage,
                owner_scope=OwnerScope.user,
                assigned_org_name="Campus Maintenance",
            ),
            DemoJobEvent(
                actor_email="coordinator@fixhub.test",
                message="Dispatch target selected; job moved to assigned",
                event_type=EventType.status_change,
                target_status=JobStatus.assigned,
                responsibility_stage=ResponsibilityStage.triage,
                owner_scope=OwnerScope.user,
                assigned_org_name="Campus Maintenance",
            ),
            DemoJobEvent(
                actor_email="triage@fixhub.test",
                message="Reviewed repeat noise history and booked maintenance to inspect the fan mount and grille.",
                event_type=EventType.status_change,
                target_status=JobStatus.triaged,
                responsibility_stage=ResponsibilityStage.triage,
                owner_scope=OwnerScope.user,
            ),
            DemoJobEvent(
                actor_email="triage@fixhub.test",
                message="Booked Maddie for Thursday 10:00-12:00 while the resident was available.",
                event_type=EventType.schedule,
                target_status=JobStatus.scheduled,
                responsibility_stage=ResponsibilityStage.coordination,
                owner_scope=OwnerScope.user,
            ),
            DemoJobEvent(
                actor_email="maintenance.contractor@fixhub.test",
                message="Tightened the loose fan grille, cleaned the housing, and tested the fan through a full run cycle.",
                event_type=EventType.completion,
                target_status=JobStatus.completed,
                responsibility_stage=ResponsibilityStage.execution,
                owner_scope=OwnerScope.user,
            ),
            DemoJobEvent(
                actor_email="resident.blockb@fixhub.test",
                message="The fan has been quiet since yesterday's visit and is working normally again.",
                reason_code="resident_confirmed_resolved",
                responsibility_stage=ResponsibilityStage.execution,
                owner_scope=OwnerScope.user,
            ),
        ),
    ),
)


def _set_job_assignment(
    *,
    job: Job,
    organisations: dict[str, Organisation],
    users: dict[str, User],
    assigned_org_name: str | None,
    assigned_contractor_email: str | None,
) -> None:
    assigned_org = organisations.get(assigned_org_name) if assigned_org_name is not None else None
    assigned_contractor = users.get(assigned_contractor_email) if assigned_contractor_email is not None else None
    if assigned_contractor is not None and assigned_org is None:
        assigned_org = assigned_contractor.organisation
    job.assigned_org = assigned_org
    job.assigned_org_id = assigned_org.id if assigned_org is not None else None
    job.assigned_contractor = assigned_contractor
    job.assigned_contractor_user_id = assigned_contractor.id if assigned_contractor is not None else None


def _report_created_message(seeded_job: DemoJob, reported_for_user: User) -> str:
    if seeded_job.intake_channel == ReportChannel.resident_portal:
        return "Resident reported the issue through the portal."
    if seeded_job.intake_channel == ReportChannel.staff_created:
        return f"Fran Front Desk logged this issue on behalf of {reported_for_user.name}."
    if seeded_job.intake_channel == ReportChannel.security_after_hours:
        return f"Fran Front Desk logged this issue through the after-hours support path for {reported_for_user.name}."
    return "Fran Front Desk logged this issue from an inspection or housekeeping round."


def _report_created_actor(seeded_job: DemoJob, reported_for_user: User, users: dict[str, User]) -> User:
    if seeded_job.intake_channel == ReportChannel.resident_portal:
        return reported_for_user
    return users["reception@fixhub.test"]


def _ensure_demo_jobs(
    session: Session,
    *,
    organisations: dict[str, Organisation],
    users: dict[str, User],
    locations: dict[str, Location],
    assets: dict[tuple[str, str], Asset],
) -> None:
    for seeded_job in DEMO_JOBS:
        reported_for_user = users[seeded_job.creator_email]
        location = locations[seeded_job.location_name]
        creator = _report_created_actor(seeded_job, reported_for_user, users)
        existing = session.scalar(
            select(Job)
            .where(
                Job.reported_for_user_id == reported_for_user.id,
                Job.location_id == location.id,
                Job.title == seeded_job.title,
            )
            .limit(1)
        )
        if existing is not None:
            continue

        asset = assets.get((seeded_job.location_name, seeded_job.asset_name)) if seeded_job.asset_name else None
        job = Job(
            title=seeded_job.title,
            description=seeded_job.description,
            organisation_id=reported_for_user.organisation_id,
            location_snapshot=location_label(location),
            asset_snapshot=asset.name if asset is not None else None,
            location_detail_text=seeded_job.location_detail_text,
            location_id=location.id,
            asset_id=asset.id if asset is not None else None,
            status=JobStatus.new,
            created_by=creator.id,
            reported_for_user_id=reported_for_user.id,
        )
        session.add(job)
        session.flush()

        append_event(
            session,
            job=job,
            actor=creator,
            message=_report_created_message(seeded_job, reported_for_user),
            event_type=EventType.report_created,
            target_status=JobStatus.new,
            reason_code=seeded_job.intake_channel.value,
            responsibility_stage=ResponsibilityStage.reception,
            owner_scope=OwnerScope.user,
        )

        for seeded_event in seeded_job.events:
            assigned_org_name = seeded_event.assigned_org_name
            if assigned_org_name is None and job.assigned_org is not None:
                assigned_org_name = job.assigned_org.name
            assigned_contractor_email = seeded_event.assigned_contractor_email
            if assigned_contractor_email is None and job.assigned_contractor is not None:
                assigned_contractor_email = job.assigned_contractor.email
            _set_job_assignment(
                job=job,
                organisations=organisations,
                users=users,
                assigned_org_name=assigned_org_name,
                assigned_contractor_email=assigned_contractor_email,
            )
            append_event(
                session,
                job=job,
                actor=users[seeded_event.actor_email],
                message=seeded_event.message,
                event_type=seeded_event.event_type,
                target_status=seeded_event.target_status,
                reason_code=seeded_event.reason_code,
                responsibility_stage=seeded_event.responsibility_stage,
                owner_scope=seeded_event.owner_scope,
            )

        sync_job_status_from_events(job)
        session.flush()


def ensure_demo_data(session: Session, *, demo_password: str) -> None:
    org_cache: dict[str, Organisation] = {}
    user_cache: dict[str, User] = {}

    for demo_org in DEMO_ORGANISATIONS:
        organisation = org_cache.get(demo_org.name)
        if organisation is None:
            organisation = session.scalar(
                select(Organisation).where(Organisation.name == demo_org.name).limit(1)
            )
        if organisation is None:
            organisation = Organisation(name=demo_org.name, type=demo_org.type)
            session.add(organisation)
            session.flush()
        organisation.type = demo_org.type
        organisation.contractor_mode = demo_org.contractor_mode
        org_cache[demo_org.name] = organisation

    for demo_org in DEMO_ORGANISATIONS:
        organisation = org_cache[demo_org.name]
        organisation.parent_org_id = (
            org_cache[demo_org.parent_name].id if demo_org.parent_name is not None else None
        )

    for demo in DEMO_USERS:
        organisation = org_cache.get(demo.organisation_name) if demo.organisation_name else None
        user = session.scalar(select(User).where(User.email == demo.email).limit(1))
        if user is None:
            user = User(
                name=demo.name,
                email=demo.email,
                role=demo.role,
                organisation_id=organisation.id if organisation else None,
            )
            session.add(user)
        else:
            user.name = demo.name
            user.role = demo.role
            user.organisation_id = organisation.id if organisation else None
        if user.password_hash is None or not verify_password(demo_password, user.password_hash):
            user.password_hash = hash_password(demo_password)
        user.is_demo_account = True
        user_cache[demo.email] = user

    session.flush()

    location_cache: dict[str, Location] = {}
    for demo_location in DEMO_LOCATIONS:
        organisation = org_cache[demo_location.organisation_name]
        location = session.scalar(
            select(Location)
            .where(
                Location.organisation_id == organisation.id,
                Location.name == demo_location.name,
            )
            .limit(1)
        )
        if location is None:
            location = Location(
                organisation_id=organisation.id,
                name=demo_location.name,
                type=demo_location.type,
            )
            session.add(location)
            session.flush()
        else:
            location.type = demo_location.type
        location_cache[demo_location.name] = location

    for demo_location in DEMO_LOCATIONS:
        location = location_cache[demo_location.name]
        location.parent_id = location_cache[demo_location.parent_name].id if demo_location.parent_name else None

    session.flush()

    asset_cache: dict[tuple[str, str], Asset] = {}
    for demo_asset in DEMO_ASSETS:
        location = location_cache[demo_asset.location_name]
        asset = session.scalar(
            select(Asset)
            .where(Asset.location_id == location.id, Asset.name == demo_asset.name)
            .limit(1)
        )
        if asset is None:
            asset = Asset(location_id=location.id, name=demo_asset.name)
            session.add(asset)
            session.flush()
        asset_cache[(demo_asset.location_name, demo_asset.name)] = asset

    session.flush()
    _ensure_demo_jobs(
        session,
        organisations=org_cache,
        users=user_cache,
        locations=location_cache,
        assets=asset_cache,
    )


def list_demo_users(session: Session) -> Sequence[User]:
    emails = [demo.email for demo in DEMO_USERS]
    users = list(session.scalars(select(User).where(User.is_demo_account.is_(True))))
    order = {email: index for index, email in enumerate(emails)}
    users.sort(key=lambda user: (order.get(user.email, len(order)), user.name))
    return users


def is_demo_user_email(email: str) -> bool:
    return email in DEMO_USER_EMAILS
