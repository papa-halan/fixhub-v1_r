from __future__ import annotations

from sqlalchemy import select

from app.models import Job
from tests.support import build_client, switch_demo_user


def seeded_job_id(app, title: str) -> str:
    with app.state.SessionLocal() as session:
        job_id = session.scalar(select(Job.id).where(Job.title == title).limit(1))
    assert job_id is not None
    return str(job_id)


def test_seeded_completed_job_clears_dispatch_before_completion(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        job_id = seeded_job_id(app, "Shower mixer leak after first repair")

        switch_demo_user(client, "resident@fixhub.test")
        detail_response = client.get(f"/api/jobs/{job_id}")
        events_response = client.get(f"/api/jobs/{job_id}/events")

    assert detail_response.status_code == 200, detail_response.text
    payload = detail_response.json()
    assert payload["status"] == "completed"
    assert payload["assigned_org_id"] is None
    assert payload["assigned_contractor_user_id"] is None
    assert payload["assignee_label"] is None

    assert events_response.status_code == 200, events_response.text
    events = events_response.json()
    assignment_cleared_index = next(i for i, event in enumerate(events) if event["message"] == "Assignment cleared")
    completion_index = next(i for i, event in enumerate(events) if event["target_status"] == "completed")

    assert assignment_cleared_index < completion_index
    assert events[assignment_cleared_index]["event_type"] == "assignment"
    assert events[assignment_cleared_index]["assigned_org_id"] is None
    assert events[assignment_cleared_index]["assigned_contractor_user_id"] is None
    assert events[assignment_cleared_index]["owner_scope"] == "user"


def test_seeded_contractor_queue_only_shows_current_dispatches(tmp_path) -> None:
    _, client = build_client(tmp_path)

    with client:
        switch_demo_user(client, "maintenance.contractor@fixhub.test")
        assigned_response = client.get("/api/jobs", params={"assigned": "true"})

    assert assigned_response.status_code == 200, assigned_response.text
    titles = [job["title"] for job in assigned_response.json()]

    assert "Shower mixer leaking again" in titles
    assert "Shower mixer leak after first repair" not in titles
    assert "Common room heater tripping overnight" not in titles
