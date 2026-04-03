from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from pydantic import ValidationError

from app.models import EventType, Job, JobStatus, Location, LocationType, User
from app.schema import EventCreate, EventRead, JobCreate, JobRead, LocationOption, LocationRead, LoginRequest
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


def test_event_create_is_note_only_and_rejects_extra_fields() -> None:
    payload = EventCreate(message="  Called resident to confirm access  ")
    assert payload.message == "Called resident to confirm access"

    with pytest.raises(ValidationError):
        EventCreate(message=" ")

    with pytest.raises(ValidationError):
        EventCreate(message="Forged completion", event_type="completion")

    with pytest.raises(ValidationError):
        EventCreate(message="Forged completion", target_status=JobStatus.completed)


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
    assert Job.__table__.c["organisation_id"].nullable is False
    assert "request_id" not in Job.__table__.c


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
        created_by=uuid.uuid4(),
        created_by_name="Riley Resident",
        assigned_org_id=None,
        assigned_org_name=None,
        assigned_contractor_user_id=None,
        assigned_contractor_name=None,
        assignee_scope=None,
        assignee_label=None,
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
