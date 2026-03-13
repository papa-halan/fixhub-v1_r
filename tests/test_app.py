from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.main import create_app


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
            "Scheduled visit tomorrow 10am",
            "Work started",
            "Job completed",
        ]
        assert [event["actor_label"] for event in events[:3]] == [
            "Resident",
            "Student Living",
            "Newcastle Plumbing",
        ]

        resident_jobs = client.get("/api/jobs?mine=true", headers=auth_headers("resident@fixhub.test"))
        assert resident_jobs.status_code == 200
        assert len(resident_jobs.json()) == 1

        resident_page = client.get(
            f"/resident/jobs/{job['id']}",
            headers=auth_headers("resident@fixhub.test"),
        )
        assert resident_page.status_code == 200
        assert "Event Timeline" in resident_page.text
        assert "Scheduled visit tomorrow 10am" in resident_page.text


def test_report_page_wires_post_form(tmp_path) -> None:
    _, client = build_client(tmp_path)

    with client:
        response = client.get("/resident/report", headers=auth_headers("resident@fixhub.test"))

    assert response.status_code == 200
    assert 'script src="/static/app.js"></script>' in response.text
    assert 'form id="report-form" class="form-grid" method="post"' in response.text
