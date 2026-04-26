from __future__ import annotations

from dataclasses import dataclass
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models import JobStatus, Location, Organisation, UserRole
from app.services import apply_status_change
from tests.support import build_client, switch_demo_user


@dataclass
class StubJob:
    status: JobStatus
    assigned_org_id: uuid.UUID | None = None
    assigned_contractor_user_id: uuid.UUID | None = None


@dataclass
class StubActor:
    role: UserRole
    organisation_id: uuid.UUID | None = None


def lookup_ids(app) -> dict[str, uuid.UUID]:
    with app.state.SessionLocal() as session:
        organisations = {
            organisation.name: organisation.id
            for organisation in session.scalars(select(Organisation).order_by(Organisation.name.asc()))
        }
        locations = {
            location.name: location.id
            for location in session.scalars(select(Location).order_by(Location.name.asc()))
        }
    return {
        "newcastle_plumbing_org_id": organisations["Newcastle Plumbing"],
        "campus_maintenance_org_id": organisations["Campus Maintenance"],
        "room_a14_location_id": locations["Block A Room 14"],
    }


def create_job(client, *, location_id: str) -> dict[str, object]:
    response = client.post(
        "/api/jobs",
        json={
            "title": "Scheduled reassignment guard",
            "description": "Tracking a lifecycle guard regression.",
            "location_id": location_id,
            "asset_name": "Sink",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_apply_status_change_rejects_no_op_target_status() -> None:
    actor = StubActor(role=UserRole.triage_officer)
    job = StubJob(status=JobStatus.scheduled, assigned_org_id=uuid.uuid4())

    with pytest.raises(HTTPException) as exc_info:
        apply_status_change(job, JobStatus.scheduled, actor, message="Still scheduled")

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "Job is already scheduled; omit status or choose a different lifecycle move"


def test_api_rejects_same_status_echo_for_active_reassignment(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)

        switch_demo_user(client, "resident@fixhub.test")
        job = create_job(client, location_id=str(ids["room_a14_location_id"]))

        switch_demo_user(client, "coordinator@fixhub.test")
        assign_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={"assigned_org_id": str(ids["newcastle_plumbing_org_id"])},
        )
        assert assign_response.status_code == 200, assign_response.text

        switch_demo_user(client, "triage@fixhub.test")
        triage_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={
                "status": "triaged",
                "event_message": "Reviewed the leak and confirmed it is ready to book.",
            },
        )
        assert triage_response.status_code == 200, triage_response.text

        schedule_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={
                "status": "scheduled",
                "event_message": "Booked plumber for Friday morning attendance.",
            },
        )
        assert schedule_response.status_code == 200, schedule_response.text
        assert schedule_response.json()["assigned_org_name"] == "Newcastle Plumbing"

        switch_demo_user(client, "admin@fixhub.test")
        no_op_reassign_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={
                "status": "scheduled",
                "assigned_org_id": str(ids["campus_maintenance_org_id"]),
            },
        )

        job_detail = client.get(f"/api/jobs/{job['id']}")
        events_response = client.get(f"/api/jobs/{job['id']}/events")

    assert no_op_reassign_response.status_code == 422
    assert no_op_reassign_response.json() == {
        "detail": "Job is already scheduled; omit status or choose a different lifecycle move"
    }

    assert job_detail.status_code == 200, job_detail.text
    payload = job_detail.json()
    assert payload["status"] == "scheduled"
    assert payload["assigned_org_name"] == "Newcastle Plumbing"

    assert events_response.status_code == 200, events_response.text
    messages = [event["message"] for event in events_response.json()]
    assert "Assigned Campus Maintenance" not in messages


def test_api_rejects_assignment_change_when_cancelling_current_dispatch(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)

        switch_demo_user(client, "resident@fixhub.test")
        job = create_job(client, location_id=str(ids["room_a14_location_id"]))

        switch_demo_user(client, "coordinator@fixhub.test")
        assign_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={"assigned_org_id": str(ids["newcastle_plumbing_org_id"])},
        )
        assert assign_response.status_code == 200, assign_response.text

        switch_demo_user(client, "triage@fixhub.test")
        triage_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={
                "status": "triaged",
                "event_message": "Reviewed the leak and confirmed it is ready to book.",
            },
        )
        assert triage_response.status_code == 200, triage_response.text

        schedule_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={
                "status": "scheduled",
                "event_message": "Booked plumber for Friday morning attendance.",
            },
        )
        assert schedule_response.status_code == 200, schedule_response.text

        switch_demo_user(client, "coordinator@fixhub.test")
        invalid_cancel_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={
                "status": "cancelled",
                "assigned_org_id": str(ids["campus_maintenance_org_id"]),
                "reason_code": "duplicate_report",
                "event_message": "Cancelled after confirming this report duplicated an existing coordination record.",
            },
        )

        job_detail = client.get(f"/api/jobs/{job['id']}")
        events_response = client.get(f"/api/jobs/{job['id']}/events")

    assert invalid_cancel_response.status_code == 422
    assert invalid_cancel_response.json() == {
        "detail": "cancelled ends the current dispatch; omit assignment fields from the same update"
    }

    assert job_detail.status_code == 200, job_detail.text
    payload = job_detail.json()
    assert payload["status"] == "scheduled"
    assert payload["assigned_org_name"] == "Newcastle Plumbing"

    assert events_response.status_code == 200, events_response.text
    messages = [event["message"] for event in events_response.json()]
    assert "Reassigned Campus Maintenance" not in messages
    assert "Assignment cleared" not in messages
    assert (
        "Cancelled after confirming this report duplicated an existing coordination record." not in messages
    )


def test_api_rejects_follow_up_without_reassignment_context_after_completion(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)

        switch_demo_user(client, "resident@fixhub.test")
        job = create_job(client, location_id=str(ids["room_a14_location_id"]))

        switch_demo_user(client, "coordinator@fixhub.test")
        assign_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={"assigned_org_id": str(ids["newcastle_plumbing_org_id"])},
        )
        assert assign_response.status_code == 200, assign_response.text

        switch_demo_user(client, "triage@fixhub.test")
        triage_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={
                "status": "triaged",
                "event_message": "Reviewed the leak and confirmed it is ready to book.",
            },
        )
        assert triage_response.status_code == 200, triage_response.text

        schedule_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={
                "status": "scheduled",
                "event_message": "Booked plumber for Friday morning attendance.",
            },
        )
        assert schedule_response.status_code == 200, schedule_response.text

        switch_demo_user(client, "contractor@fixhub.test")
        in_progress_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={
                "status": "in_progress",
                "event_message": "Contractor arrived and started tracing the leak.",
            },
        )
        assert in_progress_response.status_code == 200, in_progress_response.text

        completion_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={
                "status": "completed",
                "event_message": "Replaced the failed washer and confirmed the leak stopped.",
                "responsibility_stage": "execution",
            },
        )
        assert completion_response.status_code == 200, completion_response.text

        switch_demo_user(client, "triage@fixhub.test")
        invalid_follow_up_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={
                "status": "follow_up_scheduled",
                "reason_code": "resident_reported_recurrence",
                "event_message": "Booked a return visit after the resident reported the leak returned.",
            },
        )

        job_detail = client.get(f"/api/jobs/{job['id']}")
        events_response = client.get(f"/api/jobs/{job['id']}/events")

    assert invalid_follow_up_response.status_code == 422
    assert invalid_follow_up_response.json() == {"detail": "follow_up_scheduled requires an assignee"}

    assert job_detail.status_code == 200, job_detail.text
    payload = job_detail.json()
    assert payload["status"] == "completed"
    assert payload["assigned_org_name"] is None

    assert events_response.status_code == 200, events_response.text
    messages = [event["message"] for event in events_response.json()]
    assert "Booked a return visit after the resident reported the leak returned." not in messages
