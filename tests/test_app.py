from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select

from app.main import create_app
from app.models import Event, Job, User


def auth_headers(email: str) -> dict[str, str]:
    return {"X-User-Email": email}


def build_client(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'fixhub.db'}"
    app = create_app(database_url)
    return app, TestClient(app)


def test_schema_only_contains_four_tables(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        table_names = set(inspect(app.state.engine).get_table_names())

    assert table_names == {"events", "jobs", "organisations", "users"}


def test_api_surface_matches_mvp_scope(tmp_path) -> None:
    app, client = build_client(tmp_path)

    expected_routes = {
        ("GET", "/api/me"),
        ("POST", "/api/jobs"),
        ("GET", "/api/jobs"),
        ("GET", "/api/jobs/{job_id}"),
        ("PATCH", "/api/jobs/{job_id}"),
        ("GET", "/api/jobs/{job_id}/events"),
        ("POST", "/api/jobs/{job_id}/events"),
    }

    with client:
        api_routes = {
            (method, route.path)
            for route in app.routes
            if isinstance(route, APIRoute) and route.path.startswith("/api")
            for method in route.methods - {"HEAD", "OPTIONS"}
        }

    assert api_routes == expected_routes


def test_api_requires_known_user_header(tmp_path) -> None:
    _, client = build_client(tmp_path)

    with client:
        missing_user = client.get("/api/me")
        unknown_user = client.get("/api/me", headers=auth_headers("missing@fixhub.test"))
        resident_page = client.get("/resident/report")

    assert missing_user.status_code == 401
    assert missing_user.json() == {"detail": "X-User-Email header required"}
    assert unknown_user.status_code == 401
    assert unknown_user.json() == {"detail": "Unknown user"}
    assert resident_page.status_code == 200
    assert "View as" in resident_page.text


def test_resident_admin_contractor_flow(tmp_path) -> None:
    _, client = build_client(tmp_path)

    with client:
        contractor_me = client.get("/api/me", headers=auth_headers("contractor@fixhub.test"))
        assert contractor_me.status_code == 200
        contractor_org_id = contractor_me.json()["organisation_id"]

        create_response = client.post(
            "/api/jobs",
            headers=auth_headers("resident@fixhub.test"),
            json={
                "title": "Leaking bathroom tap",
                "description": "Water is pooling under the sink.",
                "location": "Block A Room 14",
            },
        )
        assert create_response.status_code == 201
        job = create_response.json()
        assert job["status"] == "new"

        assign_response = client.patch(
            f"/api/jobs/{job['id']}",
            headers=auth_headers("admin@fixhub.test"),
            json={"assigned_org_id": contractor_org_id},
        )
        assert assign_response.status_code == 200
        assigned_job = assign_response.json()
        assert assigned_job["status"] == "assigned"
        assert assigned_job["assigned_org_name"] == "Newcastle Plumbing"

        note_response = client.post(
            f"/api/jobs/{job['id']}/events",
            headers=auth_headers("contractor@fixhub.test"),
            json={"message": "Scheduled visit tomorrow 10am"},
        )
        assert note_response.status_code == 201

        progress_response = client.patch(
            f"/api/jobs/{job['id']}",
            headers=auth_headers("contractor@fixhub.test"),
            json={"status": "in_progress"},
        )
        assert progress_response.status_code == 200
        assert progress_response.json()["status"] == "in_progress"

        complete_response = client.patch(
            f"/api/jobs/{job['id']}",
            headers=auth_headers("contractor@fixhub.test"),
            json={"status": "completed"},
        )
        assert complete_response.status_code == 200
        assert complete_response.json()["status"] == "completed"

        events_response = client.get(
            f"/api/jobs/{job['id']}/events",
            headers=auth_headers("resident@fixhub.test"),
        )
        assert events_response.status_code == 200
        events = events_response.json()

        assert [event["message"] for event in events] == [
            "Report created",
            "Assigned Newcastle Plumbing",
            "Marked job assigned",
            "Scheduled visit tomorrow 10am",
            "Marked job in progress",
            "Marked job completed",
        ]
        assert [event["created_at"] for event in events] == sorted(event["created_at"] for event in events)
        assert events[0]["actor_name"] == "Riley Resident"
        assert events[0]["actor_role"] == "resident"
        assert events[0]["organisation_name"] == "Student Living"
        assert events[1]["actor_name"] == "Avery Admin"
        assert events[1]["actor_role"] == "admin"
        assert events[1]["organisation_name"] == "Student Living"
        assert events[3]["actor_name"] == "Devon Contractor"
        assert events[3]["actor_role"] == "contractor"
        assert events[3]["organisation_name"] == "Newcastle Plumbing"

        resident_jobs = client.get("/api/jobs?mine=true", headers=auth_headers("resident@fixhub.test"))
        assert resident_jobs.status_code == 200
        assert len(resident_jobs.json()) == 1

        resident_page = client.get(
            f"/resident/jobs/{job['id']}",
            headers=auth_headers("resident@fixhub.test"),
        )
        assert resident_page.status_code == 200
        assert "Event Timeline" in resident_page.text
        assert "Avery Admin" in resident_page.text
        assert "Newcastle Plumbing" in resident_page.text
        assert "Scheduled visit tomorrow 10am" in resident_page.text


def test_events_endpoint_returns_chronological_order(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        create_response = client.post(
            "/api/jobs",
            headers=auth_headers("resident@fixhub.test"),
            json={
                "title": "Loose wardrobe hinge",
                "description": "The hinge is pulling away from the frame.",
                "location": "Block B Room 8",
            },
        )
        assert create_response.status_code == 201
        job_id = uuid.UUID(create_response.json()["id"])

        with app.state.SessionLocal() as session:
            contractor = session.scalar(select(User).where(User.email == "contractor@fixhub.test").limit(1))
            job = session.get(Job, job_id)
            base_time = datetime.now(timezone.utc) + timedelta(minutes=5)
            session.add_all(
                [
                    Event(
                        job_id=job.id,
                        actor_user_id=contractor.id,
                        actor_org_id=contractor.organisation_id,
                        message="Inspection complete",
                        created_at=base_time + timedelta(minutes=1),
                    ),
                    Event(
                        job_id=job.id,
                        actor_user_id=contractor.id,
                        actor_org_id=contractor.organisation_id,
                        message="Waiting on spare parts",
                        created_at=base_time,
                    ),
                ]
            )
            session.commit()

        events_response = client.get(
            f"/api/jobs/{job_id}/events",
            headers=auth_headers("resident@fixhub.test"),
        )
        assert events_response.status_code == 200
        events = events_response.json()

    assert [event["message"] for event in events] == [
        "Report created",
        "Waiting on spare parts",
        "Inspection complete",
    ]


def test_report_page_wires_post_form(tmp_path) -> None:
    _, client = build_client(tmp_path)

    with client:
        response = client.get("/resident/report", headers=auth_headers("resident@fixhub.test"))

    assert response.status_code == 200
    assert 'script src="/static/app.js"></script>' in response.text
    assert 'body data-user-email="resident@fixhub.test"' in response.text
    assert 'form id="report-form" class="form-grid" method="post"' in response.text
