from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import inspect, select

from app.main import create_app
from app.models import ContractorMode, Organisation, User


def auth_headers(email: str) -> dict[str, str]:
    return {"X-User-Email": email}


def build_client(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'fixhub.db'}"
    app = create_app(database_url)
    return app, TestClient(app)


def create_job(client: TestClient, *, title: str = "Leaking bathroom tap", location: str = "Block A Room 14") -> dict[str, object]:
    response = client.post(
        "/api/jobs",
        headers=auth_headers("resident@fixhub.test"),
        json={
            "title": title,
            "description": "Water is pooling under the sink.",
            "location": location,
            "asset_name": "Sink",
        },
    )
    assert response.status_code == 201
    return response.json()


def job_events(client: TestClient, job_id: str, *, email: str = "resident@fixhub.test") -> list[dict[str, object]]:
    response = client.get(f"/api/jobs/{job_id}/events", headers=auth_headers(email))
    assert response.status_code == 200
    return response.json()


def lookup_ids(app) -> dict[str, uuid.UUID]:
    with app.state.SessionLocal() as session:
        orgs = {
            organisation.name: organisation.id
            for organisation in session.scalars(select(Organisation).order_by(Organisation.name.asc()))
        }
        users = {
            user.email: user.id for user in session.scalars(select(User).order_by(User.email.asc()))
        }
    return {
        "newcastle_plumbing_org_id": orgs["Newcastle Plumbing"],
        "campus_maintenance_org_id": orgs["Campus Maintenance"],
        "independent_contractor_user_id": users["independent.contractor@fixhub.test"],
        "org_contractor_user_id": users["contractor@fixhub.test"],
    }


def move_to_in_progress(client: TestClient, job_id: str, *, assigned_org_id: uuid.UUID) -> None:
    assign_response = client.patch(
        f"/api/jobs/{job_id}",
        headers=auth_headers("coordinator@fixhub.test"),
        json={"assigned_org_id": str(assigned_org_id)},
    )
    assert assign_response.status_code == 200
    assert assign_response.json()["status"] == "assigned"

    triage_response = client.patch(
        f"/api/jobs/{job_id}",
        headers=auth_headers("triage@fixhub.test"),
        json={"status": "triaged"},
    )
    assert triage_response.status_code == 200

    schedule_response = client.patch(
        f"/api/jobs/{job_id}",
        headers=auth_headers("triage@fixhub.test"),
        json={"status": "scheduled"},
    )
    assert schedule_response.status_code == 200

    progress_response = client.patch(
        f"/api/jobs/{job_id}",
        headers=auth_headers("contractor@fixhub.test"),
        json={"status": "in_progress"},
    )
    assert progress_response.status_code == 200


def complete_org_assigned_job(client: TestClient, job_id: str, *, assigned_org_id: uuid.UUID) -> None:
    move_to_in_progress(client, job_id, assigned_org_id=assigned_org_id)
    complete_response = client.patch(
        f"/api/jobs/{job_id}",
        headers=auth_headers("contractor@fixhub.test"),
        json={"status": "completed", "responsibility_stage": "execution"},
    )
    assert complete_response.status_code == 200


def test_schema_includes_expected_tables(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        table_names = set(inspect(app.state.engine).get_table_names())

    assert table_names == {"assets", "events", "jobs", "locations", "organisations", "users"}


def test_api_requires_known_user_header(tmp_path) -> None:
    _, client = build_client(tmp_path)

    with client:
        landing_page = client.get("/")
        missing_user = client.get("/api/me")
        unknown_user = client.get("/api/me", headers=auth_headers("missing@fixhub.test"))
        resident_page = client.get("/resident/report")

    assert landing_page.status_code == 200
    assert missing_user.status_code == 401
    assert missing_user.json() == {"detail": "X-User-Email header required"}
    assert unknown_user.status_code == 401
    assert unknown_user.json() == {"detail": "Unknown user"}
    assert resident_page.status_code == 401
    assert resident_page.json() == {"detail": "Authentication required"}


def test_demo_data_includes_org_hierarchy_and_contractor_modes(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        with app.state.SessionLocal() as session:
            student_living = session.scalar(
                select(Organisation).where(Organisation.name == "Student Living").limit(1)
            )
            university = session.scalar(
                select(Organisation).where(Organisation.name == "University of Newcastle").limit(1)
            )
            plumbing = session.scalar(
                select(Organisation).where(Organisation.name == "Newcastle Plumbing").limit(1)
            )
            maintenance = session.scalar(
                select(Organisation).where(Organisation.name == "Campus Maintenance").limit(1)
            )

    assert student_living is not None
    assert university is not None
    assert plumbing is not None
    assert maintenance is not None
    assert student_living.parent_org_id == university.id
    assert plumbing.contractor_mode == ContractorMode.external_contractor
    assert maintenance.contractor_mode == ContractorMode.maintenance_team


def test_resident_triage_schedule_execute_flow_records_structured_metadata(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        job = create_job(client)

        assign_response = client.patch(
            f"/api/jobs/{job['id']}",
            headers=auth_headers("coordinator@fixhub.test"),
            json={"assigned_org_id": str(ids["newcastle_plumbing_org_id"])},
        )
        assert assign_response.status_code == 200
        assert assign_response.json()["status"] == "assigned"
        assert assign_response.json()["assigned_org_name"] == "Newcastle Plumbing"

        triage_response = client.patch(
            f"/api/jobs/{job['id']}",
            headers=auth_headers("triage@fixhub.test"),
            json={"status": "triaged"},
        )
        assert triage_response.status_code == 200
        assert triage_response.json()["status"] == "triaged"

        schedule_response = client.patch(
            f"/api/jobs/{job['id']}",
            headers=auth_headers("triage@fixhub.test"),
            json={"status": "scheduled"},
        )
        assert schedule_response.status_code == 200
        assert schedule_response.json()["status"] == "scheduled"

        progress_response = client.patch(
            f"/api/jobs/{job['id']}",
            headers=auth_headers("contractor@fixhub.test"),
            json={"status": "in_progress"},
        )
        assert progress_response.status_code == 200

        complete_response = client.patch(
            f"/api/jobs/{job['id']}",
            headers=auth_headers("contractor@fixhub.test"),
            json={"status": "completed", "responsibility_stage": "execution"},
        )
        assert complete_response.status_code == 200
        assert complete_response.json()["status"] == "completed"

        events = job_events(client, job["id"])

    assert [event["message"] for event in events] == [
        "Report created",
        "Assigned Newcastle Plumbing",
        "Marked job assigned",
        "Marked job triaged",
        "Scheduled site visit",
        "Marked job in progress",
        "Marked job completed",
    ]
    assert events[1]["event_type"] == "assignment"
    assert events[1]["responsibility_stage"] == "triage"
    assert events[1]["owner_scope"] == "organisation"
    assert events[4]["event_type"] == "schedule"
    assert events[4]["responsibility_stage"] == "coordination"
    assert events[5]["responsibility_stage"] == "execution"
    assert events[6]["event_type"] == "completion"
    assert events[6]["responsibility_stage"] == "execution"


def test_direct_contractor_assignment_supports_independent_dispatch_and_visibility(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        job = create_job(client, title="Door closer slipping", location="Block B Room 8")

        assign_response = client.patch(
            f"/api/jobs/{job['id']}",
            headers=auth_headers("coordinator@fixhub.test"),
            json={"assigned_contractor_user_id": str(ids["independent_contractor_user_id"])},
        )
        assert assign_response.status_code == 200
        assert assign_response.json()["assigned_contractor_name"] == "Indy Independent"
        assert assign_response.json()["assignee_scope"] == "user"

        triage_response = client.patch(
            f"/api/jobs/{job['id']}",
            headers=auth_headers("triage@fixhub.test"),
            json={"status": "triaged"},
        )
        assert triage_response.status_code == 200

        schedule_response = client.patch(
            f"/api/jobs/{job['id']}",
            headers=auth_headers("triage@fixhub.test"),
            json={"status": "scheduled"},
        )
        assert schedule_response.status_code == 200

        independent_jobs = client.get("/api/jobs?assigned=true", headers=auth_headers("independent.contractor@fixhub.test"))
        org_jobs = client.get("/api/jobs?assigned=true", headers=auth_headers("contractor@fixhub.test"))
        progress_response = client.patch(
            f"/api/jobs/{job['id']}",
            headers=auth_headers("independent.contractor@fixhub.test"),
            json={"status": "in_progress"},
        )

    assert independent_jobs.status_code == 200
    assert [item["id"] for item in independent_jobs.json()] == [job["id"]]
    assert org_jobs.status_code == 200
    assert org_jobs.json() == []
    assert progress_response.status_code == 200
    assert progress_response.json()["status"] == "in_progress"


def test_clearing_assignment_moves_active_job_back_to_triaged(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        job = create_job(client, title="Loose wardrobe hinge", location="Block C Room 5")
        move_to_in_progress(client, job["id"], assigned_org_id=ids["newcastle_plumbing_org_id"])

        clear_response = client.patch(
            f"/api/jobs/{job['id']}",
            headers=auth_headers("coordinator@fixhub.test"),
            json={"assigned_org_id": None},
        )
        assert clear_response.status_code == 200
        cleared_job = clear_response.json()
        events = job_events(client, job["id"])

    assert cleared_job["status"] == "triaged"
    assert cleared_job["assigned_org_id"] is None
    assert cleared_job["assigned_contractor_user_id"] is None
    assert "Assignment cleared" in [event["message"] for event in events]
    assert "Marked job triaged" in [event["message"] for event in events]


def test_cannot_clear_assignment_and_leave_completed_state(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        job = create_job(client, title="Bathroom fan stalled", location="Block D Room 12")
        move_to_in_progress(client, job["id"], assigned_org_id=ids["newcastle_plumbing_org_id"])

        invalid_response = client.patch(
            f"/api/jobs/{job['id']}",
            headers=auth_headers("coordinator@fixhub.test"),
            json={"assigned_org_id": None, "status": "completed"},
        )

    assert invalid_response.status_code == 422
    assert invalid_response.json() == {"detail": "completed requires an assignee"}


def test_triage_and_schedule_are_role_gated(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        job = create_job(client, title="Kitchen exhaust rattling", location="Block E Kitchen")

        assign_response = client.patch(
            f"/api/jobs/{job['id']}",
            headers=auth_headers("coordinator@fixhub.test"),
            json={"assigned_org_id": str(ids["newcastle_plumbing_org_id"])},
        )
        assert assign_response.status_code == 200

        reception_triage = client.patch(
            f"/api/jobs/{job['id']}",
            headers=auth_headers("reception@fixhub.test"),
            json={"status": "triaged"},
        )
        coordinator_schedule = client.patch(
            f"/api/jobs/{job['id']}",
            headers=auth_headers("coordinator@fixhub.test"),
            json={"status": "scheduled"},
        )
        triage_response = client.patch(
            f"/api/jobs/{job['id']}",
            headers=auth_headers("triage@fixhub.test"),
            json={"status": "triaged"},
        )
        schedule_response = client.patch(
            f"/api/jobs/{job['id']}",
            headers=auth_headers("triage@fixhub.test"),
            json={"status": "scheduled"},
        )

    assert reception_triage.status_code == 403
    assert reception_triage.json() == {"detail": "Reception Admin cannot move a job to triaged"}
    assert coordinator_schedule.status_code == 403
    assert coordinator_schedule.json() == {"detail": "Coordinator cannot move a job to scheduled"}
    assert triage_response.status_code == 200
    assert schedule_response.status_code == 200


def test_follow_up_scheduled_requires_reason_code(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        job = create_job(client, title="Ceiling leak returning", location="Block F Room 3")
        complete_org_assigned_job(client, job["id"], assigned_org_id=ids["newcastle_plumbing_org_id"])

        invalid_follow_up = client.patch(
            f"/api/jobs/{job['id']}",
            headers=auth_headers("triage@fixhub.test"),
            json={"status": "follow_up_scheduled"},
        )
        valid_follow_up = client.patch(
            f"/api/jobs/{job['id']}",
            headers=auth_headers("triage@fixhub.test"),
            json={"status": "follow_up_scheduled", "reason_code": "resident_reported_recurrence"},
        )
        events = job_events(client, job["id"])

    assert invalid_follow_up.status_code == 422
    assert invalid_follow_up.json() == {
        "detail": "reason_code is required when moving a job to follow_up_scheduled"
    }
    assert valid_follow_up.status_code == 200
    assert valid_follow_up.json()["status"] == "follow_up_scheduled"
    follow_up_event = next(event for event in events if event["message"] == "Scheduled follow-up visit")
    assert follow_up_event["event_type"] == "follow_up"
    assert follow_up_event["reason_code"] == "resident_reported_recurrence"
    assert follow_up_event["responsibility_stage"] == "coordination"


def test_completed_transition_requires_explicit_accountability_metadata(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        job = create_job(client, title="Common room heater fault", location="Block J Lounge")
        move_to_in_progress(client, job["id"], assigned_org_id=ids["newcastle_plumbing_org_id"])

        invalid_complete = client.patch(
            f"/api/jobs/{job['id']}",
            headers=auth_headers("contractor@fixhub.test"),
            json={"status": "completed"},
        )
        valid_complete = client.patch(
            f"/api/jobs/{job['id']}",
            headers=auth_headers("contractor@fixhub.test"),
            json={"status": "completed", "responsibility_stage": "execution"},
        )
        events = job_events(client, job["id"], email="contractor@fixhub.test")

    assert invalid_complete.status_code == 422
    assert invalid_complete.json() == {
        "detail": "reason_code or responsibility_stage is required when moving a job to completed"
    }
    assert valid_complete.status_code == 200
    assert valid_complete.json()["status"] == "completed"
    completion_event = next(event for event in events if event["message"] == "Marked job completed")
    assert completion_event["responsibility_stage"] == "execution"


def test_blocked_transition_requires_reason_code_and_supports_reschedule(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        job = create_job(client, title="Laundry pump stalled", location="Block K Laundry")
        move_to_in_progress(client, job["id"], assigned_org_id=ids["newcastle_plumbing_org_id"])

        invalid_blocked = client.patch(
            f"/api/jobs/{job['id']}",
            headers=auth_headers("contractor@fixhub.test"),
            json={"status": "blocked"},
        )
        valid_blocked = client.patch(
            f"/api/jobs/{job['id']}",
            headers=auth_headers("contractor@fixhub.test"),
            json={"status": "blocked", "reason_code": "part_backordered"},
        )
        reschedule = client.patch(
            f"/api/jobs/{job['id']}",
            headers=auth_headers("triage@fixhub.test"),
            json={"status": "scheduled"},
        )
        events = job_events(client, job["id"], email="contractor@fixhub.test")

    assert invalid_blocked.status_code == 422
    assert invalid_blocked.json() == {"detail": "reason_code is required when moving a job to blocked"}
    assert valid_blocked.status_code == 200
    assert valid_blocked.json()["status"] == "blocked"
    assert reschedule.status_code == 200
    assert reschedule.json()["status"] == "scheduled"
    blocked_event = next(event for event in events if event["message"] == "Marked job blocked")
    assert blocked_event["reason_code"] == "part_backordered"
    assert blocked_event["responsibility_stage"] == "execution"


def test_on_hold_and_reopened_paths_require_reason_codes(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        job = create_job(client, title="Shower pressure inconsistent", location="Block L Room 7")

        assign_response = client.patch(
            f"/api/jobs/{job['id']}",
            headers=auth_headers("coordinator@fixhub.test"),
            json={"assigned_org_id": str(ids["newcastle_plumbing_org_id"])},
        )
        assert assign_response.status_code == 200

        triage_response = client.patch(
            f"/api/jobs/{job['id']}",
            headers=auth_headers("triage@fixhub.test"),
            json={"status": "triaged"},
        )
        assert triage_response.status_code == 200

        schedule_response = client.patch(
            f"/api/jobs/{job['id']}",
            headers=auth_headers("triage@fixhub.test"),
            json={"status": "scheduled"},
        )
        assert schedule_response.status_code == 200

        invalid_on_hold = client.patch(
            f"/api/jobs/{job['id']}",
            headers=auth_headers("triage@fixhub.test"),
            json={"status": "on_hold"},
        )
        valid_on_hold = client.patch(
            f"/api/jobs/{job['id']}",
            headers=auth_headers("triage@fixhub.test"),
            json={"status": "on_hold", "reason_code": "resident_requested_delay"},
        )
        back_to_scheduled = client.patch(
            f"/api/jobs/{job['id']}",
            headers=auth_headers("triage@fixhub.test"),
            json={"status": "scheduled"},
        )
        progress_response = client.patch(
            f"/api/jobs/{job['id']}",
            headers=auth_headers("contractor@fixhub.test"),
            json={"status": "in_progress"},
        )
        assert progress_response.status_code == 200

        complete_response = client.patch(
            f"/api/jobs/{job['id']}",
            headers=auth_headers("contractor@fixhub.test"),
            json={"status": "completed", "responsibility_stage": "execution"},
        )
        assert complete_response.status_code == 200

        invalid_reopen = client.patch(
            f"/api/jobs/{job['id']}",
            headers=auth_headers("coordinator@fixhub.test"),
            json={"status": "reopened"},
        )
        valid_reopen = client.patch(
            f"/api/jobs/{job['id']}",
            headers=auth_headers("coordinator@fixhub.test"),
            json={"status": "reopened", "reason_code": "resident_reported_recurrence"},
        )
        back_to_triaged = client.patch(
            f"/api/jobs/{job['id']}",
            headers=auth_headers("triage@fixhub.test"),
            json={"status": "triaged"},
        )
        events = job_events(client, job["id"])

    assert invalid_on_hold.status_code == 422
    assert invalid_on_hold.json() == {"detail": "reason_code is required when moving a job to on_hold"}
    assert valid_on_hold.status_code == 200
    assert valid_on_hold.json()["status"] == "on_hold"
    assert back_to_scheduled.status_code == 200
    assert back_to_scheduled.json()["status"] == "scheduled"
    on_hold_event = next(event for event in events if event["message"] == "Placed job on hold")
    assert on_hold_event["reason_code"] == "resident_requested_delay"
    assert on_hold_event["responsibility_stage"] == "coordination"

    assert invalid_reopen.status_code == 422
    assert invalid_reopen.json() == {"detail": "reason_code is required when moving a job to reopened"}
    assert valid_reopen.status_code == 200
    assert valid_reopen.json()["status"] == "reopened"
    assert back_to_triaged.status_code == 200
    assert back_to_triaged.json()["status"] == "triaged"
    reopened_event = next(event for event in events if event["message"] == "Reopened job")
    assert reopened_event["reason_code"] == "resident_reported_recurrence"
    assert reopened_event["responsibility_stage"] == "triage"


def test_assignment_fields_are_mutually_exclusive(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        job = create_job(client, title="Bedroom blind snapped", location="Block G Room 9")
        invalid_assignment = client.patch(
            f"/api/jobs/{job['id']}",
            headers=auth_headers("coordinator@fixhub.test"),
            json={
                "assigned_org_id": str(ids["newcastle_plumbing_org_id"]),
                "assigned_contractor_user_id": str(ids["independent_contractor_user_id"]),
            },
        )

    assert invalid_assignment.status_code == 422
    assert invalid_assignment.json() == {
        "detail": "assigned_org_id and assigned_contractor_user_id are mutually exclusive"
    }


def test_operations_job_page_includes_direct_assignment_control(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        job = create_job(client, title="Loose tap spindle", location="Block H Room 2")
        page = client.get(f"/admin/jobs/{job['id']}", headers=auth_headers("coordinator@fixhub.test"))

    assert page.status_code == 200
    assert 'name="assigned_org_id"' in page.text
    assert 'name="assigned_contractor_user_id"' in page.text
    assert "Choose either an organisation or a direct contractor." in page.text
