from __future__ import annotations

from pathlib import Path
from typing import get_args, get_origin, get_type_hints

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import create_app
from app.schema import EventCreate, EventRead, JobCreate, JobRead, JobUpdate, UserRead


def build_client(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'fixhub.db'}"
    app = create_app(database_url)
    return app, TestClient(app)


def test_schema_package_contains_expected_source_files() -> None:
    schema_dir = Path(__file__).resolve().parents[1] / "app" / "schema"

    assert schema_dir.is_dir()
    assert {path.name for path in schema_dir.glob("*.py")} >= {
        "__init__.py",
        "base.py",
        "event.py",
        "job.py",
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
    )
    assert job.title == "Leaking bathroom tap"
    assert job.description == "Water is pooling under the sink."
    assert job.location == "Block A Room 14"

    event = EventCreate(message="  Scheduled visit tomorrow 10am  ")
    assert event.message == "Scheduled visit tomorrow 10am"

    with pytest.raises(ValidationError, match="title cannot be blank"):
        JobCreate(title="   ", description="valid", location="valid")

    with pytest.raises(ValidationError, match="message cannot be blank"):
        EventCreate(message="   ")

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        JobCreate(
            title="Leaking bathroom tap",
            description="Water is pooling under the sink.",
            location="Block A Room 14",
            unexpected="value",
        )
