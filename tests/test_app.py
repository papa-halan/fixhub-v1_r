from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select

from app.main import create_app
from app.models import Asset, Event, Job, Location, Organisation, OrganisationType, User, UserRole


def auth_headers(email: str) -> dict[str, str]:
    return {"X-User-Email": email}


def build_client(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'fixhub.db'}"
    app = create_app(database_url)
    return app, TestClient(app)


def test_schema_includes_location_and_asset_tables(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        table_names = set(inspect(app.state.engine).get_table_names())

    assert table_names == {"assets", "events", "jobs", "locations", "organisations", "users"}


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
        landing_page = client.get("/")
        missing_user = client.get("/api/me")
        unknown_user = client.get("/api/me", headers=auth_headers("missing@fixhub.test"))
        resident_page = client.get("/resident/report")
        home_redirect = client.get("/", headers=auth_headers("resident@fixhub.test"), follow_redirects=False)
        demo_login = client.get(
            "/switch-user?email=resident@fixhub.test&next=/resident/report",
            follow_redirects=False,
        )
        cookie_backed_page = client.get("/resident/report")

    assert landing_page.status_code == 200
    assert "Choose a demo user to continue." in landing_page.text
    assert missing_user.status_code == 401
    assert missing_user.json() == {"detail": "X-User-Email header required"}
    assert unknown_user.status_code == 401
    assert unknown_user.json() == {"detail": "Unknown user"}
    assert resident_page.status_code == 401
    assert resident_page.json() == {"detail": "Authentication required"}
    assert home_redirect.status_code == 303
    assert home_redirect.headers["location"] == "/resident/report"
    assert demo_login.status_code == 303
    assert demo_login.headers["location"] == "/resident/report"
    assert cookie_backed_page.status_code == 200
    assert "View as" in cookie_backed_page.text


def test_role_pages_require_matching_user_role(tmp_path) -> None:
    _, client = build_client(tmp_path)

    with client:
        resident_on_admin_page = client.get("/admin/jobs", headers=auth_headers("resident@fixhub.test"))
        admin_on_contractor_page = client.get("/contractor/jobs", headers=auth_headers("admin@fixhub.test"))

    assert resident_on_admin_page.status_code == 403
    assert resident_on_admin_page.json() == {"detail": "You cannot access this page"}
    assert admin_on_contractor_page.status_code == 403
    assert admin_on_contractor_page.json() == {"detail": "You cannot access this page"}


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
    assert 'name="asset_name"' in response.text
    assert 'const rememberedLocationCatalog' in response.text


def test_resident_report_page_shows_remembered_location_and_asset_suggestions(tmp_path) -> None:
    _, client = build_client(tmp_path)

    with client:
        create_response = client.post(
            "/api/jobs",
            headers=auth_headers("resident@fixhub.test"),
            json={
                "title": "Leaking bathroom tap",
                "description": "Water is pooling under the sink.",
                "location": "Block A Room 14",
                "asset_name": "Sink",
            },
        )
        assert create_response.status_code == 201

        response = client.get("/resident/report", headers=auth_headers("resident@fixhub.test"))

    assert response.status_code == 200
    assert 'value="Block A Room 14"' in response.text
    assert "Sink" in response.text


def test_job_and_events_persist_location_and_asset_context(tmp_path) -> None:
    app, client = build_client(tmp_path)

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
                "asset_name": "Sink",
            },
        )
        assert create_response.status_code == 201
        job = create_response.json()

        assert job["location"] == "Block A Room 14"
        assert job["asset_name"] == "Sink"
        assert job["location_id"] is not None
        assert job["asset_id"] is not None

        assign_response = client.patch(
            f"/api/jobs/{job['id']}",
            headers=auth_headers("admin@fixhub.test"),
            json={"assigned_org_id": contractor_org_id},
        )
        assert assign_response.status_code == 200

        event_response = client.post(
            f"/api/jobs/{job['id']}/events",
            headers=auth_headers("contractor@fixhub.test"),
            json={"message": "Sink inspection booked"},
        )
        assert event_response.status_code == 201
        assert event_response.json()["location_id"] == job["location_id"]
        assert event_response.json()["asset_id"] == job["asset_id"]
        assert event_response.json()["location"] == "Block A Room 14"
        assert event_response.json()["asset_name"] == "Sink"

        events_response = client.get(
            f"/api/jobs/{job['id']}/events",
            headers=auth_headers("resident@fixhub.test"),
        )
        assert events_response.status_code == 200
        events = events_response.json()

        assert {event["location_id"] for event in events} == {job["location_id"]}
        assert {event["asset_id"] for event in events} == {job["asset_id"]}
        assert {event["location"] for event in events} == {"Block A Room 14"}
        assert {event["asset_name"] for event in events} == {"Sink"}

        with app.state.SessionLocal() as session:
            db_job = session.get(Job, uuid.UUID(job["id"]))
            db_location = session.get(Location, uuid.UUID(job["location_id"]))
            db_asset = session.get(Asset, uuid.UUID(job["asset_id"]))
            db_events = list(
                session.scalars(
                    select(Event).where(Event.job_id == db_job.id).order_by(Event.created_at.asc())
                )
            )

        assert db_job is not None
        assert db_location is not None
        assert db_asset is not None
        assert db_job.location_id == db_location.id
        assert db_job.asset_id == db_asset.id
        assert db_location.user_id == db_job.created_by
        assert db_asset.location_id == db_location.id
        assert {event.location_id for event in db_events} == {db_location.id}
        assert {event.asset_id for event in db_events} == {db_asset.id}


def test_admin_assignment_form_can_submit_null_org_id(tmp_path) -> None:
    _, client = build_client(tmp_path)

    with client:
        create_response = client.post(
            "/api/jobs",
            headers=auth_headers("resident@fixhub.test"),
            json={
                "title": "Light fitting loose",
                "description": "Ceiling light fitting is loose and rattling.",
                "location": "Block N Room 6",
            },
        )
        assert create_response.status_code == 201
        job_id = create_response.json()["id"]

        response = client.get(
            f"/admin/jobs/{job_id}",
            headers=auth_headers("admin@fixhub.test"),
        )

    assert response.status_code == 200
    assert '<select name="assigned_org_id">' in response.text
    assert 'No contractor assigned' in response.text
    assert 'assigned_org_id: assignedOrgId === "" ? null : assignedOrgId' in response.text


def test_admin_cannot_assign_university_org_as_contractor(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        with app.state.SessionLocal() as session:
            university_org = session.scalar(select(Organisation).where(Organisation.name == "Student Living").limit(1))
            assert university_org is not None
            assert university_org.type == OrganisationType.university

        create_response = client.post(
            "/api/jobs",
            headers=auth_headers("resident@fixhub.test"),
            json={
                "title": "No hot water",
                "description": "Shower has only cold water.",
                "location": "Block C Room 5",
            },
        )
        assert create_response.status_code == 201
        job_id = create_response.json()["id"]

        assign_response = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("admin@fixhub.test"),
            json={"assigned_org_id": str(university_org.id)},
        )

    assert assign_response.status_code == 400
    assert assign_response.json() == {"detail": "Only contractor organisations can be assigned"}


def test_admin_clearing_assignment_moves_assigned_job_back_to_new(tmp_path) -> None:
    _, client = build_client(tmp_path)

    with client:
        contractor_me = client.get("/api/me", headers=auth_headers("contractor@fixhub.test"))
        assert contractor_me.status_code == 200
        contractor_org_id = contractor_me.json()["organisation_id"]

        create_response = client.post(
            "/api/jobs",
            headers=auth_headers("resident@fixhub.test"),
            json={
                "title": "Broken blinds",
                "description": "Cannot close blinds in bedroom.",
                "location": "Block D Room 12",
            },
        )
        assert create_response.status_code == 201
        job_id = create_response.json()["id"]

        assign_response = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("admin@fixhub.test"),
            json={"assigned_org_id": contractor_org_id},
        )
        assert assign_response.status_code == 200
        assert assign_response.json()["status"] == "assigned"

        clear_response = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("admin@fixhub.test"),
            json={"assigned_org_id": None},
        )
        assert clear_response.status_code == 200
        assert clear_response.json()["status"] == "new"

        events_response = client.get(
            f"/api/jobs/{job_id}/events",
            headers=auth_headers("resident@fixhub.test"),
        )
        assert events_response.status_code == 200
        event_messages = [event["message"] for event in events_response.json()]

    assert "Assignment cleared" in event_messages
    assert "Moved job back to new" in event_messages


def test_cannot_skip_status_from_new_to_completed(tmp_path) -> None:
    _, client = build_client(tmp_path)

    with client:
        create_response = client.post(
            "/api/jobs",
            headers=auth_headers("resident@fixhub.test"),
            json={
                "title": "Window latch jammed",
                "description": "Latch does not rotate.",
                "location": "Block E Room 3",
            },
        )
        assert create_response.status_code == 201
        job_id = create_response.json()["id"]

        invalid_transition = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("admin@fixhub.test"),
            json={"status": "completed"},
        )

    assert invalid_transition.status_code == 400
    assert invalid_transition.json() == {"detail": "Cannot move job from new to completed"}


def test_independent_contractor_without_org_cannot_access_assigned_jobs(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        with app.state.SessionLocal() as session:
            independent = User(
                name="Indy Contractor",
                email="independent.contractor@fixhub.test",
                role=UserRole.contractor,
                organisation_id=None,
            )
            session.add(independent)
            session.commit()

        contractor_me = client.get("/api/me", headers=auth_headers("contractor@fixhub.test"))
        assert contractor_me.status_code == 200
        contractor_org_id = contractor_me.json()["organisation_id"]

        create_response = client.post(
            "/api/jobs",
            headers=auth_headers("resident@fixhub.test"),
            json={
                "title": "Ceiling light flicker",
                "description": "Intermittent flickering all night.",
                "location": "Block F Room 20",
            },
        )
        assert create_response.status_code == 201
        job_id = create_response.json()["id"]

        assign_response = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("admin@fixhub.test"),
            json={"assigned_org_id": contractor_org_id},
        )
        assert assign_response.status_code == 200

        independent_jobs = client.get(
            "/api/jobs?assigned=true",
            headers=auth_headers("independent.contractor@fixhub.test"),
        )
        independent_job_view = client.get(
            f"/api/jobs/{job_id}",
            headers=auth_headers("independent.contractor@fixhub.test"),
        )

    assert independent_jobs.status_code == 200
    assert independent_jobs.json() == []
    assert independent_job_view.status_code == 403
    assert independent_job_view.json() == {"detail": "You cannot access this job"}


def test_resident_cannot_view_another_resident_job(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        with app.state.SessionLocal() as session:
            student_living = session.scalar(select(Organisation).where(Organisation.name == "Student Living").limit(1))
            assert student_living is not None
            session.add(
                User(
                    name="Casey Resident",
                    email="casey.resident@fixhub.test",
                    role=UserRole.resident,
                    organisation_id=student_living.id,
                )
            )
            session.commit()

        create_response = client.post(
            "/api/jobs",
            headers=auth_headers("resident@fixhub.test"),
            json={
                "title": "Desk drawer stuck",
                "description": "The study desk drawer does not open.",
                "location": "Block G Room 9",
            },
        )
        assert create_response.status_code == 201
        job_id = create_response.json()["id"]

        forbidden_view = client.get(
            f"/api/jobs/{job_id}",
            headers=auth_headers("casey.resident@fixhub.test"),
        )

    assert forbidden_view.status_code == 403
    assert forbidden_view.json() == {"detail": "You cannot access this job"}


def test_completed_job_cannot_be_reopened_in_current_lifecycle(tmp_path) -> None:
    _, client = build_client(tmp_path)

    with client:
        contractor_me = client.get("/api/me", headers=auth_headers("contractor@fixhub.test"))
        assert contractor_me.status_code == 200
        contractor_org_id = contractor_me.json()["organisation_id"]

        create_response = client.post(
            "/api/jobs",
            headers=auth_headers("resident@fixhub.test"),
            json={
                "title": "Front door lock loose",
                "description": "The barrel wiggles and needs tightening.",
                "location": "Block H Room 2",
            },
        )
        assert create_response.status_code == 201
        job_id = create_response.json()["id"]

        assign_response = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("admin@fixhub.test"),
            json={"assigned_org_id": contractor_org_id},
        )
        assert assign_response.status_code == 200

        progress_response = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("contractor@fixhub.test"),
            json={"status": "in_progress"},
        )
        assert progress_response.status_code == 200

        complete_response = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("contractor@fixhub.test"),
            json={"status": "completed"},
        )
        assert complete_response.status_code == 200

        reopen_attempt = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("admin@fixhub.test"),
            json={"status": "in_progress"},
        )

    assert reopen_attempt.status_code == 400
    assert reopen_attempt.json() == {"detail": "Cannot move job from completed to in_progress"}


def test_admin_can_clear_assignment_while_in_progress_leaving_unassigned_work(tmp_path) -> None:
    _, client = build_client(tmp_path)

    with client:
        contractor_me = client.get("/api/me", headers=auth_headers("contractor@fixhub.test"))
        assert contractor_me.status_code == 200
        contractor_org_id = contractor_me.json()["organisation_id"]

        create_response = client.post(
            "/api/jobs",
            headers=auth_headers("resident@fixhub.test"),
            json={
                "title": "Bathroom exhaust fan rattling",
                "description": "Very noisy and intermittent.",
                "location": "Block J Room 16",
            },
        )
        assert create_response.status_code == 201
        job_id = create_response.json()["id"]

        assign_response = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("admin@fixhub.test"),
            json={"assigned_org_id": contractor_org_id},
        )
        assert assign_response.status_code == 200

        progress_response = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("contractor@fixhub.test"),
            json={"status": "in_progress"},
        )
        assert progress_response.status_code == 200

        clear_response = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("admin@fixhub.test"),
            json={"assigned_org_id": None},
        )
        assert clear_response.status_code == 200
        assert clear_response.json()["status"] == "in_progress"
        assert clear_response.json()["assigned_org_id"] is None

        events_response = client.get(
            f"/api/jobs/{job_id}/events",
            headers=auth_headers("resident@fixhub.test"),
        )
        assert events_response.status_code == 200
        messages = [event["message"] for event in events_response.json()]

    assert "Assignment cleared" in messages
    assert "Moved job back to new" not in messages


def test_contractor_can_complete_directly_from_assigned(tmp_path) -> None:
    _, client = build_client(tmp_path)

    with client:
        contractor_me = client.get("/api/me", headers=auth_headers("contractor@fixhub.test"))
        assert contractor_me.status_code == 200
        contractor_org_id = contractor_me.json()["organisation_id"]

        create_response = client.post(
            "/api/jobs",
            headers=auth_headers("resident@fixhub.test"),
            json={
                "title": "Wardrobe rail loose",
                "description": "Rail detached on one side.",
                "location": "Block K Room 4",
            },
        )
        assert create_response.status_code == 201
        job_id = create_response.json()["id"]

        assign_response = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("admin@fixhub.test"),
            json={"assigned_org_id": contractor_org_id},
        )
        assert assign_response.status_code == 200
        assert assign_response.json()["status"] == "assigned"

        complete_response = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("contractor@fixhub.test"),
            json={"status": "completed"},
        )
        assert complete_response.status_code == 200
        assert complete_response.json()["status"] == "completed"

        events_response = client.get(
            f"/api/jobs/{job_id}/events",
            headers=auth_headers("resident@fixhub.test"),
        )
        assert events_response.status_code == 200
        event_messages = [event["message"] for event in events_response.json()]

    assert "Marked job in progress" not in event_messages
    assert "Marked job completed" in event_messages


def test_admin_can_complete_job_without_contractor_status_update(tmp_path) -> None:
    _, client = build_client(tmp_path)

    with client:
        contractor_me = client.get("/api/me", headers=auth_headers("contractor@fixhub.test"))
        assert contractor_me.status_code == 200
        contractor_org_id = contractor_me.json()["organisation_id"]

        create_response = client.post(
            "/api/jobs",
            headers=auth_headers("resident@fixhub.test"),
            json={
                "title": "Kitchen cupboard hinge broken",
                "description": "Cupboard door cannot stay open.",
                "location": "Block L Room 7",
            },
        )
        assert create_response.status_code == 201
        job_id = create_response.json()["id"]

        assign_response = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("admin@fixhub.test"),
            json={"assigned_org_id": contractor_org_id},
        )
        assert assign_response.status_code == 200
        assert assign_response.json()["status"] == "assigned"

        complete_response = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("admin@fixhub.test"),
            json={"status": "completed"},
        )
        assert complete_response.status_code == 200
        assert complete_response.json()["status"] == "completed"

        resident_view = client.get(f"/api/jobs/{job_id}", headers=auth_headers("resident@fixhub.test"))
        assert resident_view.status_code == 200
        assert resident_view.json()["status"] == "completed"

        events_response = client.get(
            f"/api/jobs/{job_id}/events",
            headers=auth_headers("resident@fixhub.test"),
        )
        assert events_response.status_code == 200
        event_messages = [event["message"] for event in events_response.json()]

    assert "Marked job completed" in event_messages


def test_resident_can_add_follow_up_event_after_completion_without_reopen_path(tmp_path) -> None:
    _, client = build_client(tmp_path)

    with client:
        contractor_me = client.get("/api/me", headers=auth_headers("contractor@fixhub.test"))
        assert contractor_me.status_code == 200
        contractor_org_id = contractor_me.json()["organisation_id"]

        create_response = client.post(
            "/api/jobs",
            headers=auth_headers("resident@fixhub.test"),
            json={
                "title": "Door handle keeps coming off",
                "description": "Handle loosened again after previous repair.",
                "location": "Block M Room 11",
            },
        )
        assert create_response.status_code == 201
        job_id = create_response.json()["id"]

        assign_response = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("admin@fixhub.test"),
            json={"assigned_org_id": contractor_org_id},
        )
        assert assign_response.status_code == 200

        progress_response = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("contractor@fixhub.test"),
            json={"status": "in_progress"},
        )
        assert progress_response.status_code == 200

        complete_response = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("contractor@fixhub.test"),
            json={"status": "completed"},
        )
        assert complete_response.status_code == 200

        follow_up_event = client.post(
            f"/api/jobs/{job_id}/events",
            headers=auth_headers("resident@fixhub.test"),
            json={"message": "Issue has returned after 2 days"},
        )
        assert follow_up_event.status_code == 201
        assert follow_up_event.json()["message"] == "Issue has returned after 2 days"

        reopen_attempt = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("resident@fixhub.test"),
            json={"status": "in_progress"},
        )
        assert reopen_attempt.status_code == 403
        assert reopen_attempt.json() == {"detail": "Residents cannot update jobs"}

        resident_view = client.get(f"/api/jobs/{job_id}", headers=auth_headers("resident@fixhub.test"))
        assert resident_view.status_code == 200
        assert resident_view.json()["status"] == "completed"


def test_maintenance_team_contractor_org_can_be_assigned_and_progress_job(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        with app.state.SessionLocal() as session:
            maintenance_org = Organisation(
                name="UoN Maintenance Team",
                type=OrganisationType.contractor,
            )
            session.add(maintenance_org)
            session.flush()
            maintenance_user = User(
                name="Morgan Maintenance",
                email="maintenance.contractor@fixhub.test",
                role=UserRole.contractor,
                organisation_id=maintenance_org.id,
            )
            session.add(maintenance_user)
            session.commit()
            maintenance_org_id = str(maintenance_org.id)

        create_response = client.post(
            "/api/jobs",
            headers=auth_headers("resident@fixhub.test"),
            json={
                "title": "Study lamp fitting detached",
                "description": "The fixture hangs from one side.",
                "location": "Block N Room 18",
            },
        )
        assert create_response.status_code == 201
        job_id = create_response.json()["id"]

        assign_response = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("admin@fixhub.test"),
            json={"assigned_org_id": maintenance_org_id},
        )
        assert assign_response.status_code == 200
        assert assign_response.json()["assigned_org_name"] == "UoN Maintenance Team"

        maintenance_jobs = client.get(
            "/api/jobs?assigned=true",
            headers=auth_headers("maintenance.contractor@fixhub.test"),
        )
        assert maintenance_jobs.status_code == 200
        assert len(maintenance_jobs.json()) == 1

        progress_response = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("maintenance.contractor@fixhub.test"),
            json={"status": "in_progress"},
        )
        assert progress_response.status_code == 200
        assert progress_response.json()["status"] == "in_progress"

        complete_response = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("maintenance.contractor@fixhub.test"),
            json={"status": "completed"},
        )
        assert complete_response.status_code == 200
        assert complete_response.json()["status"] == "completed"


def test_independent_contractor_cannot_progress_job_without_org_dispatch_path(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        with app.state.SessionLocal() as session:
            independent = User(
                name="Indy NoOrg",
                email="indy.noorg@fixhub.test",
                role=UserRole.contractor,
                organisation_id=None,
            )
            session.add(independent)
            session.commit()

        contractor_me = client.get("/api/me", headers=auth_headers("contractor@fixhub.test"))
        assert contractor_me.status_code == 200
        contractor_org_id = contractor_me.json()["organisation_id"]

        create_response = client.post(
            "/api/jobs",
            headers=auth_headers("resident@fixhub.test"),
            json={
                "title": "Desk power outlet loose",
                "description": "Socket shifts when plugging in chargers.",
                "location": "Block P Room 6",
            },
        )
        assert create_response.status_code == 201
        job_id = create_response.json()["id"]

        assign_response = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("admin@fixhub.test"),
            json={"assigned_org_id": contractor_org_id},
        )
        assert assign_response.status_code == 200

        independent_progress_attempt = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("indy.noorg@fixhub.test"),
            json={"status": "in_progress"},
        )

    assert independent_progress_attempt.status_code == 403
    assert independent_progress_attempt.json() == {"detail": "You cannot access this job"}


def test_admin_can_reassign_completed_job_without_reopen_or_status_change(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        with app.state.SessionLocal() as session:
            backup_org = Organisation(
                name="Acme Electrical Contractors",
                type=OrganisationType.contractor,
            )
            session.add(backup_org)
            session.commit()
            backup_org_id = str(backup_org.id)

        contractor_me = client.get("/api/me", headers=auth_headers("contractor@fixhub.test"))
        assert contractor_me.status_code == 200
        contractor_org_id = contractor_me.json()["organisation_id"]

        create_response = client.post(
            "/api/jobs",
            headers=auth_headers("resident@fixhub.test"),
            json={
                "title": "Window frame rattling",
                "description": "Rattles loudly in wind overnight.",
                "location": "Block Q Room 1",
            },
        )
        assert create_response.status_code == 201
        job_id = create_response.json()["id"]

        assign_response = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("admin@fixhub.test"),
            json={"assigned_org_id": contractor_org_id},
        )
        assert assign_response.status_code == 200

        progress_response = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("contractor@fixhub.test"),
            json={"status": "in_progress"},
        )
        assert progress_response.status_code == 200

        complete_response = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("contractor@fixhub.test"),
            json={"status": "completed"},
        )
        assert complete_response.status_code == 200
        assert complete_response.json()["status"] == "completed"

        reassign_completed = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("admin@fixhub.test"),
            json={"assigned_org_id": backup_org_id},
        )
        assert reassign_completed.status_code == 200
        assert reassign_completed.json()["status"] == "completed"
        assert reassign_completed.json()["assigned_org_name"] == "Acme Electrical Contractors"

        events_response = client.get(
            f"/api/jobs/{job_id}/events",
            headers=auth_headers("resident@fixhub.test"),
        )
        assert events_response.status_code == 200
        messages = [event["message"] for event in events_response.json()]

    assert "Marked job completed" in messages
    assert "Reassigned Acme Electrical Contractors" in messages


def test_admin_can_complete_job_while_clearing_assignment_in_same_update(tmp_path) -> None:
    _, client = build_client(tmp_path)

    with client:
        contractor_me = client.get("/api/me", headers=auth_headers("contractor@fixhub.test"))
        assert contractor_me.status_code == 200
        contractor_org_id = contractor_me.json()["organisation_id"]

        create_response = client.post(
            "/api/jobs",
            headers=auth_headers("resident@fixhub.test"),
            json={
                "title": "Bathroom tile cracked",
                "description": "Tile edge is sharp and dangerous.",
                "location": "Block R Room 22",
            },
        )
        assert create_response.status_code == 201
        job_id = create_response.json()["id"]

        assign_response = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("admin@fixhub.test"),
            json={"assigned_org_id": contractor_org_id},
        )
        assert assign_response.status_code == 200
        assert assign_response.json()["status"] == "assigned"

        clear_and_complete_response = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("admin@fixhub.test"),
            json={
                "assigned_org_id": None,
                "status": "completed",
            },
        )
        assert clear_and_complete_response.status_code == 200
        assert clear_and_complete_response.json()["status"] == "completed"
        assert clear_and_complete_response.json()["assigned_org_id"] is None

        resident_view = client.get(
            f"/api/jobs/{job_id}",
            headers=auth_headers("resident@fixhub.test"),
        )
        assert resident_view.status_code == 200
        assert resident_view.json()["status"] == "completed"
        assert resident_view.json()["assigned_org_id"] is None

        events_response = client.get(
            f"/api/jobs/{job_id}/events",
            headers=auth_headers("resident@fixhub.test"),
        )
        assert events_response.status_code == 200
        messages = [event["message"] for event in events_response.json()]

    assert "Assignment cleared" in messages
    assert "Marked job completed" in messages


def test_admin_can_reassign_job_while_in_progress_without_handoff_status(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        with app.state.SessionLocal() as session:
            backup_org = Organisation(
                name="Rapid Facilities Group",
                type=OrganisationType.contractor,
            )
            session.add(backup_org)
            session.commit()
            backup_org_id = str(backup_org.id)

        contractor_me = client.get("/api/me", headers=auth_headers("contractor@fixhub.test"))
        assert contractor_me.status_code == 200
        contractor_org_id = contractor_me.json()["organisation_id"]

        create_response = client.post(
            "/api/jobs",
            headers=auth_headers("resident@fixhub.test"),
            json={
                "title": "Shower door won’t slide",
                "description": "Door catches halfway and jams.",
                "location": "Block S Room 13",
            },
        )
        assert create_response.status_code == 201
        job_id = create_response.json()["id"]

        assign_response = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("admin@fixhub.test"),
            json={"assigned_org_id": contractor_org_id},
        )
        assert assign_response.status_code == 200

        progress_response = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("contractor@fixhub.test"),
            json={"status": "in_progress"},
        )
        assert progress_response.status_code == 200
        assert progress_response.json()["status"] == "in_progress"

        reassign_response = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("admin@fixhub.test"),
            json={"assigned_org_id": backup_org_id},
        )
        assert reassign_response.status_code == 200
        assert reassign_response.json()["status"] == "in_progress"
        assert reassign_response.json()["assigned_org_name"] == "Rapid Facilities Group"

        events_response = client.get(
            f"/api/jobs/{job_id}/events",
            headers=auth_headers("resident@fixhub.test"),
        )
        assert events_response.status_code == 200
        messages = [event["message"] for event in events_response.json()]

    assert "Marked job in progress" in messages
    assert "Reassigned Rapid Facilities Group" in messages


def test_admin_can_close_unassigned_in_progress_job_after_contractor_loses_access(tmp_path) -> None:
    _, client = build_client(tmp_path)

    with client:
        contractor_me = client.get("/api/me", headers=auth_headers("contractor@fixhub.test"))
        assert contractor_me.status_code == 200
        contractor_org_id = contractor_me.json()["organisation_id"]

        create_response = client.post(
            "/api/jobs",
            headers=auth_headers("resident@fixhub.test"),
            json={
                "title": "Laundry room drain backing up",
                "description": "Water is spilling onto the floor near machines.",
                "location": "Block T Laundry",
            },
        )
        assert create_response.status_code == 201
        job_id = create_response.json()["id"]

        assign_response = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("admin@fixhub.test"),
            json={"assigned_org_id": contractor_org_id},
        )
        assert assign_response.status_code == 200

        progress_response = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("contractor@fixhub.test"),
            json={"status": "in_progress"},
        )
        assert progress_response.status_code == 200
        assert progress_response.json()["status"] == "in_progress"

        clear_response = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("admin@fixhub.test"),
            json={"assigned_org_id": None},
        )
        assert clear_response.status_code == 200
        assert clear_response.json()["status"] == "in_progress"
        assert clear_response.json()["assigned_org_id"] is None

        contractor_complete_attempt = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("contractor@fixhub.test"),
            json={"status": "completed"},
        )
        assert contractor_complete_attempt.status_code == 403
        assert contractor_complete_attempt.json() == {"detail": "You cannot access this job"}

        admin_complete_response = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("admin@fixhub.test"),
            json={"status": "completed"},
        )
        assert admin_complete_response.status_code == 200
        assert admin_complete_response.json()["status"] == "completed"
        assert admin_complete_response.json()["assigned_org_id"] is None

        resident_view = client.get(f"/api/jobs/{job_id}", headers=auth_headers("resident@fixhub.test"))
        assert resident_view.status_code == 200
        assert resident_view.json()["status"] == "completed"
        assert resident_view.json()["assigned_org_id"] is None

        events_response = client.get(
            f"/api/jobs/{job_id}/events",
            headers=auth_headers("resident@fixhub.test"),
        )
        assert events_response.status_code == 200
        messages = [event["message"] for event in events_response.json()]

    assert "Assignment cleared" in messages
    assert "Marked job completed" in messages


def test_single_admin_role_cannot_distinguish_reception_triage_and_coordinator_actions(tmp_path) -> None:
    _, client = build_client(tmp_path)

    with client:
        contractor_me = client.get("/api/me", headers=auth_headers("contractor@fixhub.test"))
        assert contractor_me.status_code == 200
        contractor_org_id = contractor_me.json()["organisation_id"]

        create_response = client.post(
            "/api/jobs",
            headers=auth_headers("resident@fixhub.test"),
            json={
                "title": "Entry door lock sticks",
                "description": "The lock jams and needs force to open.",
                "location": "Block U Room 2",
            },
        )
        assert create_response.status_code == 201
        job_id = create_response.json()["id"]

        assign_response = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("admin@fixhub.test"),
            json={"assigned_org_id": contractor_org_id},
        )
        assert assign_response.status_code == 200

        complete_response = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("admin@fixhub.test"),
            json={"status": "completed"},
        )
        assert complete_response.status_code == 200
        assert complete_response.json()["status"] == "completed"

        events_response = client.get(
            f"/api/jobs/{job_id}/events",
            headers=auth_headers("resident@fixhub.test"),
        )
        assert events_response.status_code == 200
        events = events_response.json()

    admin_events = [event for event in events if event["actor_name"] == "Avery Admin"]
    assert len(admin_events) >= 2
    assert {"admin"} == {event["actor_role"] for event in admin_events}
    assert {"Student Living"} == {event["organisation_name"] for event in admin_events}
    assert {"Avery Admin (Admin, Student Living)"} == {event["actor_label"] for event in admin_events}


def test_contractor_can_add_execution_note_after_completion_without_reopen_state(tmp_path) -> None:
    _, client = build_client(tmp_path)

    with client:
        contractor_me = client.get("/api/me", headers=auth_headers("contractor@fixhub.test"))
        assert contractor_me.status_code == 200
        contractor_org_id = contractor_me.json()["organisation_id"]

        create_response = client.post(
            "/api/jobs",
            headers=auth_headers("resident@fixhub.test"),
            json={
                "title": "Kitchen exhaust fan noisy",
                "description": "Fan rattles and vibrates loudly on startup.",
                "location": "Block V Shared Kitchen",
            },
        )
        assert create_response.status_code == 201
        job_id = create_response.json()["id"]

        assign_response = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("admin@fixhub.test"),
            json={"assigned_org_id": contractor_org_id},
        )
        assert assign_response.status_code == 200

        progress_response = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("contractor@fixhub.test"),
            json={"status": "in_progress"},
        )
        assert progress_response.status_code == 200

        complete_response = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("contractor@fixhub.test"),
            json={"status": "completed"},
        )
        assert complete_response.status_code == 200
        assert complete_response.json()["status"] == "completed"

        post_completion_note = client.post(
            f"/api/jobs/{job_id}/events",
            headers=auth_headers("contractor@fixhub.test"),
            json={"message": "Returning tomorrow to retighten mount bolts"},
        )
        assert post_completion_note.status_code == 201
        assert post_completion_note.json()["message"] == "Returning tomorrow to retighten mount bolts"

        resident_view = client.get(f"/api/jobs/{job_id}", headers=auth_headers("resident@fixhub.test"))
        assert resident_view.status_code == 200
        assert resident_view.json()["status"] == "completed"

        events_response = client.get(
            f"/api/jobs/{job_id}/events",
            headers=auth_headers("resident@fixhub.test"),
        )
        assert events_response.status_code == 200
        messages = [event["message"] for event in events_response.json()]

    assert "Marked job completed" in messages
    assert "Returning tomorrow to retighten mount bolts" in messages


def test_admin_can_move_assigned_job_to_in_progress_without_contractor_action(tmp_path) -> None:
    _, client = build_client(tmp_path)

    with client:
        contractor_me = client.get("/api/me", headers=auth_headers("contractor@fixhub.test"))
        assert contractor_me.status_code == 200
        contractor_org_id = contractor_me.json()["organisation_id"]

        create_response = client.post(
            "/api/jobs",
            headers=auth_headers("resident@fixhub.test"),
            json={
                "title": "Bathroom extractor fan not starting",
                "description": "Fan does not start even with lights on.",
                "location": "Block W Room 10",
            },
        )
        assert create_response.status_code == 201
        job_id = create_response.json()["id"]

        assign_response = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("admin@fixhub.test"),
            json={"assigned_org_id": contractor_org_id},
        )
        assert assign_response.status_code == 200
        assert assign_response.json()["status"] == "assigned"

        admin_progress_response = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("admin@fixhub.test"),
            json={"status": "in_progress"},
        )
        assert admin_progress_response.status_code == 200
        assert admin_progress_response.json()["status"] == "in_progress"

        events_response = client.get(
            f"/api/jobs/{job_id}/events",
            headers=auth_headers("resident@fixhub.test"),
        )
        assert events_response.status_code == 200
        events = events_response.json()

    assert "Marked job in progress" in [event["message"] for event in events]
    in_progress_event = next(event for event in events if event["message"] == "Marked job in progress")
    assert in_progress_event["actor_name"] == "Avery Admin"
    assert in_progress_event["actor_role"] == "admin"


def test_resident_full_jlc_timeline_lacks_typed_responsibility_stage_metadata(tmp_path) -> None:
    _, client = build_client(tmp_path)

    with client:
        contractor_me = client.get("/api/me", headers=auth_headers("contractor@fixhub.test"))
        assert contractor_me.status_code == 200
        contractor_org_id = contractor_me.json()["organisation_id"]

        create_response = client.post(
            "/api/jobs",
            headers=auth_headers("resident@fixhub.test"),
            json={
                "title": "Heating unit cycling off",
                "description": "Heater turns off after two minutes.",
                "location": "Block X Room 9",
            },
        )
        assert create_response.status_code == 201
        job_id = create_response.json()["id"]

        assign_response = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("admin@fixhub.test"),
            json={"assigned_org_id": contractor_org_id},
        )
        assert assign_response.status_code == 200

        admin_progress_response = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("admin@fixhub.test"),
            json={"status": "in_progress"},
        )
        assert admin_progress_response.status_code == 200

        contractor_complete_response = client.patch(
            f"/api/jobs/{job_id}",
            headers=auth_headers("contractor@fixhub.test"),
            json={"status": "completed"},
        )
        assert contractor_complete_response.status_code == 200

        events_response = client.get(
            f"/api/jobs/{job_id}/events",
            headers=auth_headers("resident@fixhub.test"),
        )
        assert events_response.status_code == 200
        events = events_response.json()

    timeline_messages = [event["message"] for event in events]
    assert "Assigned Newcastle Plumbing" in timeline_messages
    assert "Marked job assigned" in timeline_messages
    assert "Marked job in progress" in timeline_messages
    assert "Marked job completed" in timeline_messages

    responsibility_events = [
        event
        for event in events
        if event["message"] in {
            "Assigned Newcastle Plumbing",
            "Marked job assigned",
            "Marked job in progress",
            "Marked job completed",
        }
    ]
    assert len(responsibility_events) == 4
    assert {event["actor_role"] for event in responsibility_events} == {"admin", "contractor"}
    assert all("responsibility_stage" not in event for event in responsibility_events)
