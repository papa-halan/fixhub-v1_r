from __future__ import annotations

from pathlib import Path
from typing import get_args, get_origin, get_type_hints

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import create_app
from app.models import Event, Job, JobStatus, Organisation, UserRole
from app.schema import EventCreate, EventRead, JobCreate, JobRead, JobUpdate, OrganisationRead, UserRead


def build_client(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'fixhub.db'}"
    app = create_app(database_url)
    return app, TestClient(app)


def test_schema_package_contains_expected_source_files() -> None:
    schema_dir = Path(__file__).resolve().parents[1] / "app" / "schema"

    assert schema_dir.is_dir()
    assert {path.name for path in schema_dir.glob("*.py")} >= {
        "__init__.py",
        "asset.py",
        "base.py",
        "event.py",
        "job.py",
        "location.py",
        "organisation.py",
        "user.py",
    }


def test_api_routes_use_dedicated_schema_models(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        routes = {
            (method, route.path): route
            for route in app.routes
            if isinstance(route, APIRoute) and route.path.startswith("/api")
            for method in route.methods - {"HEAD", "OPTIONS"}
        }

    me_route = routes[("GET", "/api/me")]
    assert me_route.response_model is UserRead

    create_job_route = routes[("POST", "/api/jobs")]
    assert get_type_hints(create_job_route.endpoint)["payload"] is JobCreate
    assert create_job_route.response_model is JobRead

    list_jobs_route = routes[("GET", "/api/jobs")]
    assert get_origin(list_jobs_route.response_model) is list
    assert get_args(list_jobs_route.response_model) == (JobRead,)

    get_job_route = routes[("GET", "/api/jobs/{job_id}")]
    assert get_job_route.response_model is JobRead

    update_job_route = routes[("PATCH", "/api/jobs/{job_id}")]
    assert get_type_hints(update_job_route.endpoint)["payload"] is JobUpdate
    assert update_job_route.response_model is JobRead

    list_events_route = routes[("GET", "/api/jobs/{job_id}/events")]
    assert get_origin(list_events_route.response_model) is list
    assert get_args(list_events_route.response_model) == (EventRead,)

    create_event_route = routes[("POST", "/api/jobs/{job_id}/events")]
    assert get_type_hints(create_event_route.endpoint)["payload"] is EventCreate
    assert create_event_route.response_model is EventRead


def test_request_schemas_strip_and_validate_text_fields() -> None:
    job = JobCreate(
        title="  Leaking bathroom tap  ",
        description="  Water is pooling under the sink.  ",
        location="  Block A Room 14  ",
        asset_name="  Sink  ",
    )
    assert job.title == "Leaking bathroom tap"
    assert job.description == "Water is pooling under the sink."
    assert job.location == "Block A Room 14"
    assert job.asset_name == "Sink"

    event = EventCreate(message="  Scheduled visit tomorrow 10am  ", reason_code="  access_confirmed  ")
    assert event.message == "Scheduled visit tomorrow 10am"
    assert event.reason_code == "access_confirmed"

    job_update = JobUpdate(reason_code="  follow_up_required  ")
    assert job_update.reason_code == "follow_up_required"

    with pytest.raises(ValidationError, match="title cannot be blank"):
        JobCreate(title="   ", description="valid", location="valid")

    with pytest.raises(ValidationError, match="message cannot be blank"):
        EventCreate(message="   ")

    with pytest.raises(ValidationError, match="asset_name cannot be blank"):
        JobCreate(title="valid", description="valid", location="valid", asset_name="   ")

    with pytest.raises(ValidationError, match="reason_code cannot be blank"):
        EventCreate(message="valid", reason_code="   ")

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        JobCreate(
            title="Leaking bathroom tap",
            description="Water is pooling under the sink.",
            location="Block A Room 14",
            unexpected="value",
        )


def test_user_role_enum_includes_student_living_operational_sub_roles() -> None:
    assert {role.value for role in UserRole} == {
        "resident",
        "admin",
        "reception_admin",
        "triage_officer",
        "coordinator",
        "contractor",
    }


def test_job_status_enum_supports_refined_operational_lifecycle() -> None:
    assert {status.value for status in JobStatus} == {
        "new",
        "assigned",
        "triaged",
        "scheduled",
        "in_progress",
        "on_hold",
        "blocked",
        "completed",
        "cancelled",
        "reopened",
        "follow_up_scheduled",
        "escalated",
    }


def test_job_table_supports_org_or_direct_contractor_assignment() -> None:
    job_columns = set(Job.__table__.columns.keys())

    assert "assigned_org_id" in job_columns
    assert "assigned_contractor_user_id" in job_columns
    assert "assigned_user_id" not in job_columns


def test_event_table_supports_structured_accountability_metadata() -> None:
    event_columns = set(Event.__table__.columns.keys())

    assert "event_type" in event_columns
    assert "reason_code" in event_columns
    assert "responsibility_stage" in event_columns
    assert "owner_scope" in event_columns


def test_organisation_table_supports_hierarchy_and_contractor_modes() -> None:
    organisation_columns = set(Organisation.__table__.columns.keys())

    assert "parent_org_id" in organisation_columns
    assert "contractor_mode" in organisation_columns


def test_read_models_surface_assignment_and_accountability_fields() -> None:
    assert "assigned_contractor_user_id" in JobRead.model_fields
    assert "assigned_contractor_name" in JobRead.model_fields
    assert "assignee_scope" in JobRead.model_fields

    assert "event_type" in EventRead.model_fields
    assert "responsibility_stage" in EventRead.model_fields
    assert "owner_scope" in EventRead.model_fields

    assert "parent_org_id" in OrganisationRead.model_fields
    assert "contractor_mode" in OrganisationRead.model_fields
