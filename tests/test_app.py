from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select

from app.main import create_app
from app.models import (
    Base,
    ContractorMode,
    Location,
    LocationType,
    Organisation,
    OrganisationType,
    User,
    UserRole,
)
from app.services.passwords import hash_password
from tests.support import (
    DEMO_PASSWORD,
    build_client,
    build_settings,
    login_as,
    logout,
    sqlite_database_url,
    switch_demo_user,
)


EXPECTED_TABLES = {
    "alembic_version",
    "assets",
    "events",
    "jobs",
    "locations",
    "organisations",
    "users",
}


def lookup_ids(app) -> dict[str, uuid.UUID]:
    with app.state.SessionLocal() as session:
        orgs = {
            organisation.name: organisation.id
            for organisation in session.scalars(select(Organisation).order_by(Organisation.name.asc()))
        }
        users = {
            user.email: user.id for user in session.scalars(select(User).order_by(User.email.asc()))
        }
        locations = {
            location.name: location.id
            for location in session.scalars(select(Location).order_by(Location.name.asc()))
        }
    return {
        "student_living_org_id": orgs["Student Living"],
        "newcastle_plumbing_org_id": orgs["Newcastle Plumbing"],
        "campus_maintenance_org_id": orgs["Campus Maintenance"],
        "independent_contractors_org_id": orgs["Independent Contractors"],
        "independent_contractor_user_id": users["independent.contractor@fixhub.test"],
        "org_contractor_user_id": users["contractor@fixhub.test"],
        "room_a14_location_id": locations["Block A Room 14"],
        "room_b8_location_id": locations["Block B Room 8"],
        "common_room_location_id": locations["Block A Common Room"],
        "building_a_location_id": locations["Block A"],
        "campus_location_id": locations["Callaghan Campus"],
    }


def create_job(
    client: TestClient,
    *,
    location_id: uuid.UUID,
    title: str = "Leaking bathroom tap",
    asset_name: str = "Sink",
    location_detail_text: str | None = None,
) -> dict[str, object]:
    response = client.post(
        "/api/jobs",
        json={
            "title": title,
            "description": "Water is pooling under the sink.",
            "location_id": str(location_id),
            "location_detail_text": location_detail_text,
            "asset_name": asset_name,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def job_events(client: TestClient, job_id: str) -> list[dict[str, object]]:
    response = client.get(f"/api/jobs/{job_id}/events")
    assert response.status_code == 200, response.text
    return response.json()


def move_to_in_progress(client: TestClient, job_id: str, *, assigned_org_id: uuid.UUID) -> None:
    switch_demo_user(client, "coordinator@fixhub.test")
    assign_response = client.patch(
        f"/api/jobs/{job_id}",
        json={"assigned_org_id": str(assigned_org_id)},
    )
    assert assign_response.status_code == 200, assign_response.text
    assert assign_response.json()["status"] == "assigned"

    switch_demo_user(client, "triage@fixhub.test")
    triage_response = client.patch(
        f"/api/jobs/{job_id}",
        json={"status": "triaged"},
    )
    assert triage_response.status_code == 200, triage_response.text

    schedule_response = client.patch(
        f"/api/jobs/{job_id}",
        json={"status": "scheduled"},
    )
    assert schedule_response.status_code == 200, schedule_response.text

    switch_demo_user(client, "contractor@fixhub.test")
    progress_response = client.patch(
        f"/api/jobs/{job_id}",
        json={"status": "in_progress"},
    )
    assert progress_response.status_code == 200, progress_response.text


def complete_org_assigned_job(client: TestClient, job_id: str, *, assigned_org_id: uuid.UUID) -> None:
    move_to_in_progress(client, job_id, assigned_org_id=assigned_org_id)
    complete_response = client.patch(
        f"/api/jobs/{job_id}",
        json={"status": "completed", "responsibility_stage": "execution"},
    )
    assert complete_response.status_code == 200, complete_response.text


def test_migrated_app_boots_with_expected_tables(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        table_names = set(inspect(app.state.engine).get_table_names())

    assert table_names == EXPECTED_TABLES


def test_page_requests_redirect_to_login_when_unauthenticated(tmp_path) -> None:
    _, client = build_client(tmp_path)

    with client:
        response = client.get("/resident/report", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/?next=/resident/report"


def test_demo_auth_is_disabled_by_default(tmp_path) -> None:
    _, client = build_client(tmp_path, demo_mode=False, seed_demo_data=False)

    with client:
        landing_page = client.get("/")
        switch_user = client.get(
            "/switch-user",
            params={"email": "resident@fixhub.test", "next": "/resident/report"},
            follow_redirects=False,
        )
        login_response = client.post(
            "/login",
            json={
                "email": "resident@fixhub.test",
                "password": DEMO_PASSWORD,
                "next_path": "/resident/report",
            },
            follow_redirects=False,
        )
        api_me = client.get("/api/me")

    assert landing_page.status_code == 200
    assert "Demo Shortcuts" not in landing_page.text
    assert "Shared demo password" not in landing_page.text
    assert switch_user.status_code == 404
    assert login_response.status_code == 303
    assert login_response.headers["location"] == "/?next=/login"
    assert api_me.status_code == 401
    assert api_me.json() == {"detail": "Authentication required"}


def test_login_sets_cookie_and_allows_api_and_page_access(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        login_response = login_as(client, "resident@fixhub.test", next_path="/resident/report")
        api_me = client.get("/api/me")
        report_page = client.get("/resident/report")
        logout(client)
        api_after_logout = client.get("/api/me")

    assert login_response.json() == {"redirect_path": "/resident/report"}
    assert client.cookies.get(app.state.settings.session_cookie_name) is None
    assert api_me.status_code == 200
    assert api_me.json()["email"] == "resident@fixhub.test"
    assert report_page.status_code == 200
    assert "Create Job" in report_page.text
    assert api_after_logout.status_code == 401


def test_startup_requires_migrated_schema(tmp_path) -> None:
    database_url = sqlite_database_url(tmp_path / "bootstrap_required.db")
    app = create_app(
        settings_override=build_settings(
            database_url,
            demo_mode=False,
            seed_demo_data=False,
        )
    )

    with pytest.raises(RuntimeError, match="Run `alembic upgrade head`"):
        with TestClient(app):
            pass


def test_startup_does_not_call_create_all(tmp_path, monkeypatch) -> None:
    def fail_create_all(*args, **kwargs):
        raise AssertionError("create_all should not be called during app startup")

    monkeypatch.setattr(Base.metadata, "create_all", fail_create_all)
    _, client = build_client(tmp_path)

    with client:
        response = client.get("/")

    assert response.status_code == 200


def test_demo_data_includes_passwords_org_hierarchy_location_hierarchy_and_independent_org(tmp_path) -> None:
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
            independent_org = session.scalar(
                select(Organisation).where(Organisation.name == "Independent Contractors").limit(1)
            )
            resident = session.scalar(select(User).where(User.email == "resident@fixhub.test").limit(1))
            independent_user = session.scalar(
                select(User).where(User.email == "independent.contractor@fixhub.test").limit(1)
            )
            room = session.scalar(select(Location).where(Location.name == "Block A Room 14").limit(1))
            building = session.scalar(select(Location).where(Location.name == "Block A").limit(1))

    assert student_living is not None
    assert university is not None
    assert plumbing is not None
    assert maintenance is not None
    assert independent_org is not None
    assert resident is not None
    assert independent_user is not None
    assert room is not None
    assert building is not None
    assert student_living.parent_org_id == university.id
    assert plumbing.contractor_mode == ContractorMode.external_contractor
    assert maintenance.contractor_mode == ContractorMode.maintenance_team
    assert resident.password_hash is not None
    assert resident.is_demo_account is True
    assert independent_user.organisation_id == independent_org.id
    assert room.type == LocationType.unit
    assert room.parent_id == building.id


def test_resident_report_page_lists_reportable_locations_only(tmp_path) -> None:
    _, client = build_client(tmp_path)

    with client:
        login_as(client, "resident@fixhub.test", next_path="/resident/report")
        report_page = client.get("/resident/report")

    assert report_page.status_code == 200
    assert "Block A Room 14" in report_page.text
    assert "Block B Laundry" in report_page.text
    assert "Callaghan Campus" not in report_page.text
    assert "Sink" in report_page.text


def test_report_creation_rejects_non_reportable_and_cross_org_location_usage(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        login_as(client, "resident@fixhub.test")

        invalid_type_response = client.post(
            "/api/jobs",
            json={
                "title": "Should fail",
                "description": "Buildings are not directly reportable.",
                "location_id": str(ids["building_a_location_id"]),
                "asset_name": "Pump",
            },
        )

        with app.state.SessionLocal() as session:
            contractor_location = Location(
                organisation_id=ids["newcastle_plumbing_org_id"],
                name="Plumbing Warehouse",
                type=LocationType.space,
            )
            session.add(contractor_location)
            session.commit()
            session.refresh(contractor_location)

        cross_org_response = client.post(
            "/api/jobs",
            json={
                "title": "Should also fail",
                "description": "Cross-org location should not be allowed.",
                "location_id": str(contractor_location.id),
                "asset_name": "Pump",
            },
        )

    assert invalid_type_response.status_code == 422
    assert invalid_type_response.json() == {"detail": "Choose a valid location"}
    assert cross_org_response.status_code == 422
    assert cross_org_response.json() == {"detail": "Choose a valid location"}


def test_same_org_access_rules_block_other_org_admins_from_viewing_jobs(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        switch_demo_user(client, "resident@fixhub.test")
        job = create_job(client, location_id=ids["room_a14_location_id"])
        logout(client)

        with app.state.SessionLocal() as session:
            outsider_org = Organisation(name="Harbour Housing", type=OrganisationType.university)
            outsider_user = User(
                name="Harriet Housing",
                email="harriet.housing@fixhub.test",
                role=UserRole.admin,
                organisation=outsider_org,
                password_hash=hash_password("other-password"),
                is_demo_account=False,
            )
            session.add_all([outsider_org, outsider_user])
            session.commit()

        login_as(client, "harriet.housing@fixhub.test", password="other-password")
        response = client.get(f"/api/jobs/{job['id']}")

    assert response.status_code == 403
    assert response.json() == {"detail": "You cannot access this job"}


def test_resident_triage_schedule_execute_flow_records_structured_metadata(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        switch_demo_user(client, "resident@fixhub.test")
        job = create_job(
            client,
            location_id=ids["room_a14_location_id"],
            location_detail_text="Near the bathroom door",
        )

        switch_demo_user(client, "coordinator@fixhub.test")
        assign_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={"assigned_org_id": str(ids["newcastle_plumbing_org_id"])},
        )
        assert assign_response.status_code == 200, assign_response.text
        assert assign_response.json()["status"] == "assigned"
        assert assign_response.json()["assigned_org_name"] == "Newcastle Plumbing"

        switch_demo_user(client, "triage@fixhub.test")
        triage_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={"status": "triaged"},
        )
        assert triage_response.status_code == 200, triage_response.text

        schedule_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={"status": "scheduled"},
        )
        assert schedule_response.status_code == 200, schedule_response.text

        switch_demo_user(client, "contractor@fixhub.test")
        progress_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={"status": "in_progress"},
        )
        assert progress_response.status_code == 200, progress_response.text

        complete_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={"status": "completed", "responsibility_stage": "execution"},
        )
        assert complete_response.status_code == 200, complete_response.text

        switch_demo_user(client, "resident@fixhub.test")
        final_job = client.get(f"/api/jobs/{job['id']}")
        events = job_events(client, job["id"])

    assert final_job.status_code == 200
    assert final_job.json()["organisation_id"] == str(ids["student_living_org_id"])
    assert final_job.json()["location_id"] == str(ids["room_a14_location_id"])
    assert final_job.json()["location_detail_text"] == "Near the bathroom door"
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
    assert events[2]["event_type"] == "status_change"
    assert events[6]["event_type"] == "completion"


def test_direct_contractor_assignment_supports_independent_dispatch_and_visibility(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        switch_demo_user(client, "resident@fixhub.test")
        job = create_job(
            client,
            location_id=ids["room_b8_location_id"],
            title="Door closer slipping",
            asset_name="Door Closer",
        )

        switch_demo_user(client, "coordinator@fixhub.test")
        assign_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={"assigned_contractor_user_id": str(ids["independent_contractor_user_id"])},
        )
        assert assign_response.status_code == 200, assign_response.text

        switch_demo_user(client, "triage@fixhub.test")
        triage_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={"status": "triaged"},
        )
        assert triage_response.status_code == 200, triage_response.text

        schedule_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={"status": "scheduled"},
        )
        assert schedule_response.status_code == 200, schedule_response.text

        switch_demo_user(client, "independent.contractor@fixhub.test")
        independent_jobs = client.get("/api/jobs?assigned=true")
        progress_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={"status": "in_progress"},
        )

        switch_demo_user(client, "contractor@fixhub.test")
        org_jobs = client.get("/api/jobs?assigned=true")

    assert independent_jobs.status_code == 200
    assert [item["id"] for item in independent_jobs.json()] == [job["id"]]
    assert progress_response.status_code == 200
    assert progress_response.json()["status"] == "in_progress"
    assert org_jobs.status_code == 200
    assert org_jobs.json() == []


def test_clearing_assignment_moves_active_job_back_to_triaged(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        switch_demo_user(client, "resident@fixhub.test")
        job = create_job(
            client,
            location_id=ids["common_room_location_id"],
            title="Loose wardrobe hinge",
            asset_name="Heater",
        )
        move_to_in_progress(client, job["id"], assigned_org_id=ids["newcastle_plumbing_org_id"])

        switch_demo_user(client, "coordinator@fixhub.test")
        clear_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={"assigned_org_id": None},
        )
        assert clear_response.status_code == 200, clear_response.text
        cleared_job = clear_response.json()

        switch_demo_user(client, "resident@fixhub.test")
        events = job_events(client, job["id"])

    assert cleared_job["status"] == "triaged"
    assert cleared_job["assigned_org_id"] is None
    assert "Assignment cleared" in [event["message"] for event in events]
    assert "Marked job triaged" in [event["message"] for event in events]


def test_triage_and_schedule_are_role_gated(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        switch_demo_user(client, "resident@fixhub.test")
        job = create_job(
            client,
            location_id=ids["room_a14_location_id"],
            title="Kitchen exhaust rattling",
        )

        switch_demo_user(client, "coordinator@fixhub.test")
        assign_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={"assigned_org_id": str(ids["newcastle_plumbing_org_id"])},
        )
        assert assign_response.status_code == 200, assign_response.text

        switch_demo_user(client, "reception@fixhub.test")
        reception_triage = client.patch(
            f"/api/jobs/{job['id']}",
            json={"status": "triaged"},
        )

        switch_demo_user(client, "coordinator@fixhub.test")
        coordinator_schedule = client.patch(
            f"/api/jobs/{job['id']}",
            json={"status": "scheduled"},
        )

        switch_demo_user(client, "triage@fixhub.test")
        triage_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={"status": "triaged"},
        )
        schedule_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={"status": "scheduled"},
        )

    assert reception_triage.status_code == 403
    assert coordinator_schedule.status_code == 403
    assert triage_response.status_code == 200
    assert schedule_response.status_code == 200


def test_follow_up_requires_reason_and_cannot_complete_without_returning_to_in_progress(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        switch_demo_user(client, "resident@fixhub.test")
        job = create_job(client, location_id=ids["room_a14_location_id"], title="Ceiling leak returning")
        complete_org_assigned_job(client, job["id"], assigned_org_id=ids["newcastle_plumbing_org_id"])

        switch_demo_user(client, "triage@fixhub.test")
        invalid_follow_up = client.patch(
            f"/api/jobs/{job['id']}",
            json={"status": "follow_up_scheduled"},
        )
        valid_follow_up = client.patch(
            f"/api/jobs/{job['id']}",
            json={"status": "follow_up_scheduled", "reason_code": "resident_reported_recurrence"},
        )

        switch_demo_user(client, "contractor@fixhub.test")
        invalid_complete = client.patch(
            f"/api/jobs/{job['id']}",
            json={"status": "completed", "responsibility_stage": "execution"},
        )

    assert invalid_follow_up.status_code == 422
    assert valid_follow_up.status_code == 200
    assert invalid_complete.status_code == 400
    assert invalid_complete.json() == {
        "detail": "Cannot move job from follow_up_scheduled to completed"
    }


def test_manual_event_endpoint_is_note_only_and_residents_cannot_add_events(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        switch_demo_user(client, "resident@fixhub.test")
        job = create_job(client, location_id=ids["room_a14_location_id"])
        resident_event = client.post(
            f"/api/jobs/{job['id']}/events",
            json={"message": "Need extra update"},
        )

        switch_demo_user(client, "coordinator@fixhub.test")
        invalid_structured_event = client.post(
            f"/api/jobs/{job['id']}/events",
            json={"message": "Forged completion", "event_type": "completion"},
        )
        valid_note = client.post(
            f"/api/jobs/{job['id']}/events",
            json={"message": "Called resident to confirm access"},
        )

    assert resident_event.status_code == 403
    assert resident_event.json() == {"detail": "Residents cannot add timeline events"}
    assert invalid_structured_event.status_code == 422
    assert "Extra inputs are not permitted" in invalid_structured_event.text
    assert valid_note.status_code == 201
    assert valid_note.json()["event_type"] == "note"


def test_operations_job_page_includes_direct_assignment_control_with_demo_switch(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        switch_demo_user(client, "resident@fixhub.test")
        job = create_job(client, location_id=ids["room_a14_location_id"], title="Loose tap spindle")

        switch_demo_user(client, "coordinator@fixhub.test", next_path=f"/admin/jobs/{job['id']}")
        page = client.get(f"/admin/jobs/{job['id']}")

    assert page.status_code == 200
    assert 'name="assigned_org_id"' in page.text
    assert 'name="assigned_contractor_user_id"' in page.text
    assert "Choose either an organisation or a direct contractor." in page.text
