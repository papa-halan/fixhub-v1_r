from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from pydantic import ValidationError

from app.models import (
    EventType,
    Job,
    JobStatus,
    Location,
    LocationType,
    OwnerScope,
    ResidentUpdateReason,
    ResponsibilityOwner,
    ResponsibilityStage,
    User,
)
from app.schema import (
    EventCreate,
    EventRead,
    JobCreate,
    JobRead,
    JobUpdate,
    LocationOption,
    LocationRead,
    LoginRequest,
    ResidentUpdateCreate,
)
from app.services.passwords import hash_password, verify_password


def test_job_create_requires_structured_location_and_trims_fields() -> None:
    location_id = uuid.uuid4()

    payload = JobCreate(
        title="  Leaking tap  ",
        description="  Water under sink  ",
        location_id=location_id,
        location_detail_text="  Near the bathroom door  ",
        asset_name="  Sink  ",
    )

    assert payload.title == "Leaking tap"
    assert payload.description == "Water under sink"
    assert payload.location_id == location_id
    assert payload.location_detail_text == "Near the bathroom door"
    assert payload.asset_name == "Sink"

    with pytest.raises(ValidationError):
        JobCreate(
            title=" ",
            description="Still descriptive",
            location_id=location_id,
        )

    with pytest.raises(ValidationError):
        JobCreate(
            title="Missing location",
            description="No location id supplied",
        )


def test_event_create_accepts_structured_note_metadata_but_rejects_status_fields() -> None:
    payload = EventCreate(
        message="  Called resident to confirm access  ",
        reason_code="  awaiting_access  ",
        responsibility_stage=ResponsibilityStage.coordination,
        owner_scope=OwnerScope.organisation,
        responsibility_owner=ResponsibilityOwner.coordinator,
    )
    assert payload.message == "Called resident to confirm access"
    assert payload.reason_code == "awaiting_access"
    assert payload.responsibility_stage == ResponsibilityStage.coordination
    assert payload.owner_scope == OwnerScope.organisation
    assert payload.responsibility_owner == ResponsibilityOwner.coordinator

    with pytest.raises(ValidationError):
        EventCreate(message=" ")

    with pytest.raises(ValidationError):
        EventCreate(message="Forged completion", event_type="completion")

    with pytest.raises(ValidationError):
        EventCreate(message="Forged completion", target_status=JobStatus.completed)


def test_job_update_trims_event_message() -> None:
    payload = JobUpdate(
        status=JobStatus.scheduled,
        event_message="  Resident approved Friday access  ",
        responsibility_owner=ResponsibilityOwner.contractor,
    )

    assert payload.event_message == "Resident approved Friday access"
    assert payload.responsibility_owner == ResponsibilityOwner.contractor

    with pytest.raises(ValidationError):
        JobUpdate(status=JobStatus.scheduled, event_message=" ")


def test_event_read_includes_optional_target_status() -> None:
    event = EventRead(
        id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        location_id=None,
        location=None,
        asset_id=None,
        asset_name=None,
        actor_user_id=uuid.uuid4(),
        actor_org_id=None,
        actor_name="Riley Resident",
        actor_role=None,
        actor_role_label=None,
        organisation_name=None,
        assigned_org_id=uuid.uuid4(),
        assigned_org_name="Newcastle Plumbing",
        assigned_contractor_user_id=None,
        assigned_contractor_name=None,
        actor_label="Riley Resident",
        event_type=EventType.completion,
        target_status=JobStatus.completed,
        message="Marked job completed",
        reason_code=None,
        responsibility_stage=None,
        owner_scope=None,
        responsibility_owner=None,
        created_at=datetime.now(timezone.utc),
    )

    assert event.target_status == JobStatus.completed
    assert event.assigned_org_name == "Newcastle Plumbing"


def test_resident_update_create_only_accepts_structured_pilot_reason_codes() -> None:
    payload = ResidentUpdateCreate(
        message="  Please avoid 1-2pm because the room is locked  ",
        reason_code="resident_access_update",
    )

    assert payload.message == "Please avoid 1-2pm because the room is locked"
    assert payload.reason_code == ResidentUpdateReason.resident_access_update

    resolved_payload = ResidentUpdateCreate(
        message="The issue has stayed fixed since the last visit",
        reason_code="resident_confirmed_resolved",
    )

    assert resolved_payload.reason_code == ResidentUpdateReason.resident_confirmed_resolved

    with pytest.raises(ValidationError):
        ResidentUpdateCreate(
            message="Missing structured reason",
        )

    with pytest.raises(ValidationError):
        ResidentUpdateCreate(
            message="Please avoid 1-2pm because the room is locked",
            reason_code="access_changed_again",
        )


def test_login_request_trims_credentials() -> None:
    payload = LoginRequest(
        email=" resident@fixhub.test ",
        password=" fixhub-demo-password ",
        next_path="/resident/report",
    )

    assert payload.email == "resident@fixhub.test"
    assert payload.password == "fixhub-demo-password"
    assert payload.next_path == "/resident/report"


def test_password_hash_round_trip() -> None:
    password_hash = hash_password("fixhub-demo-password")

    assert password_hash.startswith("scrypt$")
    assert verify_password("fixhub-demo-password", password_hash) is True
    assert verify_password("wrong-password", password_hash) is False
    assert verify_password("fixhub-demo-password", None) is False


def test_phase_zero_point_five_model_columns_are_present_without_phase_one_fields() -> None:
    assert "password_hash" in User.__table__.c
    assert "is_demo_account" in User.__table__.c
    assert User.__table__.c["is_demo_account"].nullable is False

    assert "parent_id" in Location.__table__.c
    assert "type" in Location.__table__.c
    assert Location.__table__.c["type"].nullable is False

    assert "organisation_id" in Job.__table__.c
    assert "location_detail_text" in Job.__table__.c
    assert "asset_snapshot" in Job.__table__.c
    assert "reported_for_user_id" in Job.__table__.c
    assert Job.__table__.c["organisation_id"].nullable is False
    assert "request_id" not in Job.__table__.c
    assert "assigned_org_id" in EventRead.model_fields
    assert "assigned_contractor_user_id" in EventRead.model_fields
    assert "action_required_summary" in JobRead.model_fields
    assert "visit_plan_headline" in JobRead.model_fields
    assert "visit_booking_message" in JobRead.model_fields


def test_location_and_job_read_models_include_phase_zero_point_five_fields() -> None:
    timestamp = datetime.now(timezone.utc)
    organisation_id = uuid.uuid4()
    location_id = uuid.uuid4()

    location = LocationRead(
        id=location_id,
        organisation_id=organisation_id,
        parent_id=uuid.uuid4(),
        name="Block A Room 14",
        type=LocationType.unit,
        created_at=timestamp,
    )
    job = JobRead(
        id=uuid.uuid4(),
        title="Leaking tap",
        description="Water under sink",
        organisation_id=organisation_id,
        location="Block A Room 14",
        location_id=location_id,
        location_detail_text="Near the bathroom door",
        asset_id=None,
        asset_name="Sink",
        status=JobStatus.new,
        status_label="New",
        coordination_headline="New report waiting for intake review",
        coordination_owner_label="Front desk",
        coordination_detail=None,
        action_required_by="Front desk",
        action_required_summary="Review the report and hand it into triage or dispatch.",
        responsibility_stage=None,
        owner_scope=None,
        created_by=uuid.uuid4(),
        created_by_name="Fran Front Desk",
        reported_for_user_id=uuid.uuid4(),
        reported_for_user_name="Riley Resident",
        responsibility_owner=None,
        assigned_org_id=None,
        assigned_org_name=None,
        assigned_contractor_user_id=None,
        assigned_contractor_name=None,
        assignee_scope=None,
        assignee_label=None,
        latest_event_type=None,
        latest_event_actor_label=None,
        latest_event_at=None,
        latest_lifecycle_event_type=None,
        latest_lifecycle_event_actor_label=None,
        latest_lifecycle_event_at=None,
        latest_resident_update_message=None,
        latest_resident_update_actor_label=None,
        latest_resident_update_at=None,
        latest_operations_update_message=None,
        latest_operations_update_actor_label=None,
        latest_operations_update_at=None,
        latest_contractor_update_message=None,
        latest_contractor_update_actor_label=None,
        latest_contractor_update_at=None,
        created_at=timestamp,
        updated_at=timestamp,
    )
    option = LocationOption(id=location_id, parent_id=None, name="Block B Laundry", type=LocationType.space)

    assert location.organisation_id == organisation_id
    assert location.type == LocationType.unit
    assert job.organisation_id == organisation_id
    assert job.location_id == location_id
    assert job.location_detail_text == "Near the bathroom door"
    assert option.assets == []
