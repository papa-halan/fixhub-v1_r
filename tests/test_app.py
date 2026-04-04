from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select

from app.main import create_app
from app.models import (
    Base,
    ContractorMode,
    Event,
    Job,
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
        "maintenance_contractor_user_id": users["maintenance.contractor@fixhub.test"],
        "org_contractor_user_id": users["contractor@fixhub.test"],
        "room_a14_location_id": locations["Block A Room 14"],
        "room_b8_location_id": locations["Block B Room 8"],
        "common_room_location_id": locations["Block A Common Room"],
        "building_a_location_id": locations["Block A"],
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
    assert assign_response.json()["status"] == "new"

    switch_demo_user(client, "triage@fixhub.test")
    triage_response = client.patch(
        f"/api/jobs/{job_id}",
        json={"status": "triaged"},
    )
    assert triage_response.status_code == 200, triage_response.text

    schedule_response = client.patch(
        f"/api/jobs/{job_id}",
        json={"status": "scheduled", "event_message": "Resident approved Tuesday morning access window"},
    )
    assert schedule_response.status_code == 200, schedule_response.text

    switch_demo_user(client, "contractor@fixhub.test")
    progress_response = client.patch(
        f"/api/jobs/{job_id}",
        json={"status": "in_progress", "event_message": "Contractor attended site and started diagnosing the leak"},
    )
    assert progress_response.status_code == 200, progress_response.text


def complete_org_assigned_job(client: TestClient, job_id: str, *, assigned_org_id: uuid.UUID) -> None:
    move_to_in_progress(client, job_id, assigned_org_id=assigned_org_id)
    complete_response = client.patch(
        f"/api/jobs/{job_id}",
        json={
            "status": "completed",
            "event_message": "Tap washer replaced and sink tested with no further leak",
            "responsibility_stage": "execution",
        },
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


def test_job_events_are_sorted_by_timestamp_then_id_for_stable_timeline_reads(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        switch_demo_user(client, "resident@fixhub.test")
        job = create_job(client, location_id=lookup_ids(app)["room_a14_location_id"])

        switch_demo_user(client, "reception@fixhub.test")
        note_one = client.post(
            f"/api/jobs/{job['id']}/events",
            json={"message": "Confirmed resident availability"},
        )
        note_two = client.post(
            f"/api/jobs/{job['id']}/events",
            json={"message": "Requested plumber attendance window"},
        )
        assert note_one.status_code == 201, note_one.text
        assert note_two.status_code == 201, note_two.text

        shared_created_at = datetime(2026, 4, 4, 0, 0, tzinfo=timezone.utc)
        with app.state.SessionLocal() as session:
            events = list(session.scalars(select(Event).where(Event.job_id == uuid.UUID(job["id"]))))
            for event in events:
                event.created_at = shared_created_at
            session.commit()

        events = job_events(client, job["id"])

    returned_ids = [event["id"] for event in events]
    assert returned_ids == sorted(returned_ids)


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
            data={
                "email": "resident@fixhub.test",
                "password": DEMO_PASSWORD,
                "next_path": "/resident/report",
            },
        )
        api_me = client.get("/api/me")

    assert landing_page.status_code == 200
    assert "Demo Shortcuts" not in landing_page.text
    assert "Local demo password" not in landing_page.text
    assert switch_user.status_code == 404
    assert login_response.status_code == 401
    assert "Invalid email or password" in login_response.text
    assert api_me.status_code == 401
    assert api_me.json() == {"detail": "Authentication required"}


def test_normal_mode_bootstrap_login_sets_cookie_and_allows_access(tmp_path) -> None:
    app, client = build_client(
        tmp_path,
        demo_mode=False,
        seed_demo_data=False,
        bootstrap_user_email="ops.admin@example.com",
        bootstrap_user_password="ops-password",
        bootstrap_user_name="Olivia Operations",
        bootstrap_user_org_name="Harbour Housing",
    )

    with client:
        landing_page = client.get("/")
        login_response = client.post(
            "/login",
            data={
                "email": "ops.admin@example.com",
                "password": "ops-password",
                "next_path": "/admin/jobs",
            },
            follow_redirects=False,
        )
        api_me = client.get("/api/me")
        queue_page = client.get("/admin/jobs")
        home_redirect = client.get("/", follow_redirects=False)
        logout(client)
        api_after_logout = client.get("/api/me")

    assert landing_page.status_code == 200
    assert "Demo Shortcuts" not in landing_page.text
    assert login_response.status_code == 303
    assert login_response.headers["location"] == "/admin/jobs"
    assert api_me.status_code == 200
    assert api_me.json()["email"] == "ops.admin@example.com"
    assert queue_page.status_code == 200
    assert "System Admin" in queue_page.text
    assert "Demo view" not in queue_page.text
    assert home_redirect.status_code == 303
    assert home_redirect.headers["location"] == "/admin/jobs"
    assert client.cookies.get(app.state.settings.session_cookie_name) is None
    assert api_after_logout.status_code == 401


def test_normal_mode_can_log_in_seeded_demo_users_without_demo_shortcuts(tmp_path) -> None:
    app, client = build_client(
        tmp_path,
        demo_mode=False,
        seed_demo_data=True,
        bootstrap_user_email="ops.admin@example.com",
        bootstrap_user_password="ops-password",
    )

    with client:
        landing_page = client.get("/")
        switch_user = client.get(
            "/switch-user",
            params={"email": "resident@fixhub.test", "next": "/resident/report"},
            follow_redirects=False,
        )
        login_response = client.post(
            "/login",
            data={
                "email": "resident@fixhub.test",
                "password": DEMO_PASSWORD,
                "next_path": "/resident/report",
            },
            follow_redirects=False,
        )
        api_me = client.get("/api/me")
        report_page = client.get("/resident/report")
        home_redirect = client.get("/", follow_redirects=False)
        logout(client)
        api_after_logout = client.get("/api/me")

    assert landing_page.status_code == 200
    assert "Demo Shortcuts" not in landing_page.text
    assert "Local demo password" not in landing_page.text
    assert switch_user.status_code == 404
    assert login_response.status_code == 303
    assert login_response.headers["location"] == "/resident/report"
    assert api_me.status_code == 200
    assert api_me.json()["email"] == "resident@fixhub.test"
    assert report_page.status_code == 200
    assert "Demo view" not in report_page.text
    assert home_redirect.status_code == 303
    assert home_redirect.headers["location"] == "/resident/report"
    assert client.cookies.get(app.state.settings.session_cookie_name) is None
    assert api_after_logout.status_code == 401


def test_login_failure_renders_inline_error_in_normal_mode(tmp_path) -> None:
    app, client = build_client(
        tmp_path,
        demo_mode=False,
        seed_demo_data=False,
        bootstrap_user_email="ops.admin@example.com",
        bootstrap_user_password="ops-password",
    )

    with client:
        response = client.post(
            "/login",
            data={
                "email": "ops.admin@example.com",
                "password": "wrong-password",
                "next_path": "/admin/jobs",
            },
        )

    assert response.status_code == 401
    assert "Invalid email or password" in response.text
    assert "ops.admin@example.com" in response.text
    assert client.cookies.get(app.state.settings.session_cookie_name) is None


def test_demo_switcher_visible_only_in_demo_mode(tmp_path) -> None:
    _, client = build_client(tmp_path)

    with client:
        landing_page = client.get("/")
        login_as(client, "resident@fixhub.test", next_path="/resident/report")
        report_page = client.get("/resident/report")

    assert landing_page.status_code == 200
    assert "Demo Shortcuts" in landing_page.text
    assert "Local demo password" in landing_page.text
    assert report_page.status_code == 200
    assert "Demo view" in report_page.text


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


def test_demo_data_includes_passwords_org_hierarchy_location_hierarchy_and_contractor_orgs(tmp_path) -> None:
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
            resident = session.scalar(select(User).where(User.email == "resident@fixhub.test").limit(1))
            maintenance_user = session.scalar(
                select(User).where(User.email == "maintenance.contractor@fixhub.test").limit(1)
            )
            room = session.scalar(select(Location).where(Location.name == "Block A Room 14").limit(1))
            building = session.scalar(select(Location).where(Location.name == "Block A").limit(1))

    assert student_living is not None
    assert university is not None
    assert plumbing is not None
    assert maintenance is not None
    assert resident is not None
    assert maintenance_user is not None
    assert room is not None
    assert building is not None
    assert student_living.parent_org_id == university.id
    assert plumbing.contractor_mode == ContractorMode.external_contractor
    assert maintenance.contractor_mode == ContractorMode.maintenance_team
    assert resident.password_hash is not None
    assert resident.is_demo_account is True
    assert maintenance_user.organisation_id == maintenance.id
    assert room.type == LocationType.unit
    assert room.parent_id == building.id


def test_resident_report_page_lists_reportable_locations_only(tmp_path) -> None:
    _, client = build_client(tmp_path)

    with client:
        login_as(client, "resident@fixhub.test", next_path="/resident/report")
        report_page = client.get("/resident/report")

    assert report_page.status_code == 200
    assert "Callaghan Campus &gt; Block A &gt; Block A Room 14" in report_page.text
    assert "Callaghan Campus &gt; Block B &gt; Block B Laundry" in report_page.text
    assert ">Callaghan Campus</option>" not in report_page.text
    assert "Sink" in report_page.text
    assert "Leave asset blank if you only know the location." in report_page.text


def test_legacy_placeholder_locations_are_hidden_from_catalog_and_rejected(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        with app.state.SessionLocal() as session:
            legacy_location = Location(
                organisation_id=ids["student_living_org_id"],
                name="a",
                type=LocationType.space,
            )
            session.add(legacy_location)
            session.commit()
            session.refresh(legacy_location)

        login_as(client, "resident@fixhub.test", next_path="/resident/report")
        report_page = client.get("/resident/report")
        create_response = client.post(
            "/api/jobs",
            json={
                "title": "Should fail",
                "description": "Legacy placeholder locations are not reportable.",
                "location_id": str(legacy_location.id),
                "asset_name": "Pump",
            },
        )

    assert report_page.status_code == 200
    assert ">a</option>" not in report_page.text
    assert create_response.status_code == 422
    assert create_response.json() == {"detail": "Choose a valid location"}


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
            contractor_building = Location(
                organisation_id=ids["newcastle_plumbing_org_id"],
                name="Plumbing Depot",
                type=LocationType.building,
            )
            session.add(contractor_building)
            session.flush()
            contractor_location = Location(
                organisation_id=ids["newcastle_plumbing_org_id"],
                name="Plumbing Warehouse",
                type=LocationType.space,
                parent_id=contractor_building.id,
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


def test_report_creation_keeps_asset_optional_and_rejects_unknown_asset_names(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        login_as(client, "resident@fixhub.test")

        no_asset_response = client.post(
            "/api/jobs",
            json={
                "title": "Ceiling stain spreading",
                "description": "Water mark is spreading above the desk.",
                "location_id": str(ids["room_a14_location_id"]),
                "asset_name": None,
            },
        )
        unknown_asset_response = client.post(
            "/api/jobs",
            json={
                "title": "Unknown fixture issue",
                "description": "Resident cannot identify the affected fixture.",
                "location_id": str(ids["room_a14_location_id"]),
                "asset_name": "Mystery Pipe",
            },
        )

    assert no_asset_response.status_code == 201
    assert no_asset_response.json()["asset_id"] is None
    assert no_asset_response.json()["asset_name"] is None
    assert unknown_asset_response.status_code == 422
    assert unknown_asset_response.json() == {
        "detail": "Choose a known asset for that location or leave asset_name blank"
    }


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

        login_as(client, "harriet.housing@fixhub.test", password="other-password", next_path="/admin/jobs")
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
        assert assign_response.json()["status"] == "new"
        assert assign_response.json()["assigned_org_name"] == "Newcastle Plumbing"

        switch_demo_user(client, "triage@fixhub.test")
        triage_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={"status": "triaged"},
        )
        assert triage_response.status_code == 200, triage_response.text

        schedule_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={"status": "scheduled", "event_message": "Resident approved Tuesday morning access window"},
        )
        assert schedule_response.status_code == 200, schedule_response.text

        switch_demo_user(client, "contractor@fixhub.test")
        progress_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={"status": "in_progress", "event_message": "Contractor attended site and started diagnosing the leak"},
        )
        assert progress_response.status_code == 200, progress_response.text

        complete_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={
                "status": "completed",
                "event_message": "Tap washer replaced and sink tested with no further leak",
                "responsibility_stage": "execution",
            },
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
        "Triage review recorded",
        "Resident approved Tuesday morning access window",
        "Contractor attended site and started diagnosing the leak",
        "Tap washer replaced and sink tested with no further leak",
    ]
    assert events[1]["event_type"] == "assignment"
    assert events[2]["event_type"] == "status_change"
    assert events[5]["event_type"] == "completion"
    assert events[1]["assigned_org_id"] == str(ids["newcastle_plumbing_org_id"])
    assert events[1]["assigned_org_name"] == "Newcastle Plumbing"
    assert events[4]["assigned_org_id"] == str(ids["newcastle_plumbing_org_id"])
    assert events[4]["assigned_org_name"] == "Newcastle Plumbing"
    assert events[6]["assigned_org_id"] == str(ids["newcastle_plumbing_org_id"])
    assert [event["target_status"] for event in events] == [
        "new",
        None,
        "triaged",
        "scheduled",
        "in_progress",
        "completed",
    ]
    assert final_job.json()["status"] == events[-1]["target_status"]
    assert final_job.json()["coordination_headline"] == "Work marked complete"
    assert final_job.json()["coordination_owner_label"] == "Resident"
    assert final_job.json()["coordination_detail"] == "Tap washer replaced and sink tested with no further leak"
    assert final_job.json()["responsibility_stage"] == "execution"
    assert final_job.json()["latest_event_type"] == "completion"


def test_direct_contractor_assignment_supports_named_technician_dispatch_and_visibility(tmp_path) -> None:
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
            json={"assigned_contractor_user_id": str(ids["maintenance_contractor_user_id"])},
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
            json={"status": "scheduled", "event_message": "Campus maintenance technician confirmed Thursday arrival"},
        )
        assert schedule_response.status_code == 200, schedule_response.text

        switch_demo_user(client, "maintenance.contractor@fixhub.test")
        technician_jobs = client.get("/api/jobs?assigned=true")
        progress_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={"status": "in_progress", "event_message": "Technician attended site and started adjusting the closer"},
        )

        switch_demo_user(client, "resident@fixhub.test")
        events = job_events(client, job["id"])

        switch_demo_user(client, "contractor@fixhub.test")
        org_jobs = client.get("/api/jobs?assigned=true")

    assert technician_jobs.status_code == 200
    assert [item["id"] for item in technician_jobs.json()] == [job["id"]]
    assert technician_jobs.json()[0]["assigned_org_name"] == "Campus Maintenance"
    assert technician_jobs.json()[0]["assigned_contractor_name"] == "Maddie Maintenance Technician"
    assert progress_response.status_code == 200
    assert progress_response.json()["status"] == "in_progress"
    assert progress_response.json()["assigned_org_name"] == "Campus Maintenance"
    assert progress_response.json()["assigned_contractor_name"] == "Maddie Maintenance Technician"
    assert events[1]["assigned_contractor_user_id"] == str(ids["maintenance_contractor_user_id"])
    assert events[1]["assigned_contractor_name"] == "Maddie Maintenance Technician"
    assert events[-1]["assigned_contractor_user_id"] == str(ids["maintenance_contractor_user_id"])
    assert org_jobs.status_code == 200
    assert org_jobs.json() == []


def test_direct_contractor_assignment_requires_contractor_org_membership_and_ui_hides_invalid_users(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        with app.state.SessionLocal() as session:
            housing_org = Organisation(name="Harbour Housing", type=OrganisationType.university)
            rogue_contractor = User(
                name="Rogue Contractor",
                email="rogue.contractor@fixhub.test",
                role=UserRole.contractor,
                organisation=housing_org,
                password_hash=hash_password("rogue-password"),
                is_demo_account=False,
            )
            session.add_all([housing_org, rogue_contractor])
            session.commit()
            session.refresh(rogue_contractor)

        switch_demo_user(client, "resident@fixhub.test")
        job = create_job(client, location_id=ids["room_a14_location_id"], title="Ceiling vent vibrating")

        switch_demo_user(client, "coordinator@fixhub.test", next_path=f"/admin/jobs/{job['id']}")
        page = client.get(f"/admin/jobs/{job['id']}")
        invalid_assign_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={"assigned_contractor_user_id": str(rogue_contractor.id)},
        )

    assert page.status_code == 200
    assert "Rogue Contractor" not in page.text
    assert invalid_assign_response.status_code == 422
    assert invalid_assign_response.json() == {
        "detail": "Direct contractors must belong to a contractor organisation"
    }


def test_named_contractor_assignment_keeps_contractor_org_context_and_can_fall_back_to_org_level(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        switch_demo_user(client, "resident@fixhub.test")
        job = create_job(client, location_id=ids["room_a14_location_id"], title="Shower mixer loose")

        switch_demo_user(client, "coordinator@fixhub.test", next_path=f"/admin/jobs/{job['id']}")
        assign_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={"assigned_contractor_user_id": str(ids["org_contractor_user_id"])},
        )
        assert assign_response.status_code == 200, assign_response.text

        job_page = client.get(f"/admin/jobs/{job['id']}")
        resident_view = client.get(f"/api/jobs/{job['id']}")

        fallback_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={"assigned_contractor_user_id": None},
        )
        assert fallback_response.status_code == 200, fallback_response.text

    assert assign_response.json()["assigned_org_name"] == "Newcastle Plumbing"
    assert assign_response.json()["assigned_contractor_name"] == "Devon Contractor"
    assert assign_response.json()["assignee_label"] == "Devon Contractor"
    assert job_page.status_code == 200
    assert "Choosing a direct contractor keeps that contractor&#39;s organisation attached for accountable dispatch." in job_page.text
    assert resident_view.status_code == 200
    assert resident_view.json()["assigned_org_name"] == "Newcastle Plumbing"
    assert resident_view.json()["assigned_contractor_name"] == "Devon Contractor"
    assert fallback_response.json()["assigned_org_name"] == "Newcastle Plumbing"
    assert fallback_response.json()["assigned_contractor_name"] is None


def test_job_read_uses_assignment_history_when_job_row_drifts(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        switch_demo_user(client, "resident@fixhub.test")
        job = create_job(client, location_id=ids["room_a14_location_id"], title="Dispatch drift check")

        switch_demo_user(client, "coordinator@fixhub.test")
        assign_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={"assigned_contractor_user_id": str(ids["org_contractor_user_id"])},
        )
        assert assign_response.status_code == 200, assign_response.text

        with app.state.SessionLocal() as session:
            record = session.scalar(select(Job).where(Job.id == uuid.UUID(job["id"])).limit(1))
            assert record is not None
            record.assigned_org_id = ids["campus_maintenance_org_id"]
            record.assigned_contractor_user_id = None
            session.commit()

        resident_view = client.get(f"/api/jobs/{job['id']}")

    assert resident_view.status_code == 200
    assert resident_view.json()["assigned_org_name"] == "Newcastle Plumbing"
    assert resident_view.json()["assigned_contractor_name"] == "Devon Contractor"
    assert resident_view.json()["assignee_label"] == "Devon Contractor"


def test_contractor_visibility_uses_assignment_history_when_job_row_drifts(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        switch_demo_user(client, "resident@fixhub.test")
        job = create_job(client, location_id=ids["room_a14_location_id"], title="Window latch loose")

        switch_demo_user(client, "coordinator@fixhub.test")
        assign_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={"assigned_contractor_user_id": str(ids["org_contractor_user_id"])},
        )
        assert assign_response.status_code == 200, assign_response.text

        with app.state.SessionLocal() as session:
            record = session.scalar(select(Job).where(Job.id == uuid.UUID(job["id"])).limit(1))
            assert record is not None
            record.assigned_org_id = ids["campus_maintenance_org_id"]
            record.assigned_contractor_user_id = ids["maintenance_contractor_user_id"]
            session.commit()

        switch_demo_user(client, "contractor@fixhub.test")
        assigned_jobs = client.get("/api/jobs?assigned=true")
        job_detail = client.get(f"/api/jobs/{job['id']}")

    assert assigned_jobs.status_code == 200
    assert [item["id"] for item in assigned_jobs.json()] == [job["id"]]
    assert job_detail.status_code == 200
    assert job_detail.json()["assigned_org_name"] == "Newcastle Plumbing"
    assert job_detail.json()["assigned_contractor_name"] == "Devon Contractor"


def test_clearing_active_assignment_requires_explicit_lifecycle_update(tmp_path) -> None:
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
        clear_without_status = client.patch(
            f"/api/jobs/{job['id']}",
            json={"assigned_org_id": None},
        )
        assert clear_without_status.status_code == 422, clear_without_status.text

        clear_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={
                "assigned_org_id": None,
                "status": "on_hold",
                "reason_code": "reassigning_after_failed_attendance",
                "event_message": "Attendance failed and dispatch must choose a new contractor before booking again",
            },
        )
        assert clear_response.status_code == 200, clear_response.text
        cleared_job = clear_response.json()

        switch_demo_user(client, "resident@fixhub.test")
        events = job_events(client, job["id"])

    assert clear_without_status.json() == {
        "detail": (
            "Assignment changes while a job is in_progress require an explicit lifecycle update "
            "so the timeline shows how attendance or field ownership changed"
        )
    }
    assert cleared_job["status"] == "on_hold"
    assert cleared_job["assigned_org_id"] is None
    assert "Assignment cleared" in [event["message"] for event in events]
    assert "Attendance failed and dispatch must choose a new contractor before booking again" in [
        event["message"] for event in events
    ]
    assert next(event for event in events if event["message"] == "Assignment cleared")["target_status"] is None
    assert next(event for event in events if event["message"] == "Assignment cleared")["assigned_org_id"] is None
    assert next(
        event
        for event in events
        if event["message"] == "Attendance failed and dispatch must choose a new contractor before booking again"
    )["target_status"] == "on_hold"
    assert next(
        event
        for event in events
        if event["message"] == "Attendance failed and dispatch must choose a new contractor before booking again"
    )["assigned_org_id"] is None
    assert cleared_job["status"] == next(
        event["target_status"] for event in reversed(events) if event["target_status"] is not None
    )


def test_clearing_assigned_dispatch_requires_explicit_lifecycle_update(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        switch_demo_user(client, "resident@fixhub.test")
        job = create_job(client, location_id=ids["room_a14_location_id"], title="Loose basin waste")

        switch_demo_user(client, "coordinator@fixhub.test")
        assign_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={"assigned_org_id": str(ids["newcastle_plumbing_org_id"]), "status": "assigned"},
        )
        assert assign_response.status_code == 200, assign_response.text

        clear_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={"assigned_org_id": None},
        )

    assert clear_response.status_code == 422
    assert clear_response.json() == {
        "detail": (
            "Clearing the dispatch target while a job is assigned requires an explicit lifecycle "
            "update so the visible status still matches who is carrying the work"
        )
    }


def test_update_job_uses_event_derived_status_when_job_row_drifts(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        switch_demo_user(client, "resident@fixhub.test")
        job = create_job(client, location_id=ids["room_a14_location_id"], title="Shower head leaking")
        move_to_in_progress(client, job["id"], assigned_org_id=ids["newcastle_plumbing_org_id"])

        with app.state.SessionLocal() as session:
            record = session.scalar(select(Job).where(Job.id == uuid.UUID(job["id"])).limit(1))
            assert record is not None
            record.status = "new"
            session.commit()

        switch_demo_user(client, "contractor@fixhub.test")
        complete_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={
                "status": "completed",
                "event_message": "Replaced shower head washer and confirmed leak stopped",
                "responsibility_stage": "execution",
            },
        )

        switch_demo_user(client, "resident@fixhub.test")
        events = job_events(client, job["id"])

    assert complete_response.status_code == 200, complete_response.text
    assert complete_response.json()["status"] == "completed"
    assert events[-1]["target_status"] == "completed"


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
            json={"status": "scheduled", "event_message": "Resident approved access for the first attendance window"},
        )

        switch_demo_user(client, "triage@fixhub.test")
        triage_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={"status": "triaged"},
        )
        schedule_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={"status": "scheduled", "event_message": "Resident approved access for the first attendance window"},
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
            json={
                "status": "follow_up_scheduled",
                "reason_code": "resident_reported_recurrence",
                "event_message": "Resident reported the leak returned after the first repair",
            },
        )

        switch_demo_user(client, "contractor@fixhub.test")
        invalid_complete = client.patch(
            f"/api/jobs/{job['id']}",
            json={
                "status": "completed",
                "event_message": "Contractor attempted to close the recurrence without a return visit",
                "responsibility_stage": "execution",
            },
        )

    assert invalid_follow_up.status_code == 422
    assert invalid_follow_up.json() == {
        "detail": "event_message is required when moving a job to follow_up_scheduled"
    }
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
            json={
                "message": "Called resident to confirm access",
                "reason_code": "awaiting_access",
                "responsibility_stage": "coordination",
            },
        )

    assert resident_event.status_code == 403
    assert resident_event.json() == {"detail": "Residents cannot add timeline events"}
    assert invalid_structured_event.status_code == 422
    assert "Extra inputs are not permitted" in invalid_structured_event.text
    assert valid_note.status_code == 201
    assert valid_note.json()["event_type"] == "note"
    assert valid_note.json()["target_status"] is None
    assert valid_note.json()["reason_code"] == "awaiting_access"
    assert valid_note.json()["responsibility_stage"] == "coordination"


def test_structured_note_updates_coordination_signal_without_fake_status_change(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        switch_demo_user(client, "resident@fixhub.test")
        job = create_job(client, location_id=ids["room_a14_location_id"])

        switch_demo_user(client, "coordinator@fixhub.test")
        assign_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={"assigned_org_id": str(ids["newcastle_plumbing_org_id"])},
        )
        assert assign_response.status_code == 200, assign_response.text

        switch_demo_user(client, "triage@fixhub.test")
        triage_response = client.patch(f"/api/jobs/{job['id']}", json={"status": "triaged"})
        assert triage_response.status_code == 200, triage_response.text
        schedule_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={"status": "scheduled", "event_message": "Resident approved Tuesday morning access window"},
        )
        assert schedule_response.status_code == 200, schedule_response.text

        note_response = client.post(
            f"/api/jobs/{job['id']}/events",
            json={
                "message": "Resident asked to move the access window after the original booking",
                "reason_code": "resident_access_issue",
                "responsibility_stage": "coordination",
            },
        )
        assert note_response.status_code == 201, note_response.text

        resident_view = client.get(f"/api/jobs/{job['id']}")
        events = job_events(client, job["id"])

    assert resident_view.status_code == 200
    assert resident_view.json()["status"] == "scheduled"
    assert resident_view.json()["coordination_headline"] == (
        "Coordination follow-up recorded without changing lifecycle state"
    )
    assert resident_view.json()["coordination_owner_label"] == "Dispatch coordinator"
    assert resident_view.json()["coordination_detail"] == (
        "Resident asked to move the access window after the original booking"
    )
    assert events[-1]["target_status"] is None
    assert events[-1]["reason_code"] == "resident_access_issue"


def test_assignment_only_change_surfaces_as_dispatch_update_without_fake_progress(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        switch_demo_user(client, "resident@fixhub.test")
        job = create_job(client, location_id=ids["room_a14_location_id"])

        switch_demo_user(client, "coordinator@fixhub.test")
        first_assign = client.patch(
            f"/api/jobs/{job['id']}",
            json={"assigned_org_id": str(ids["newcastle_plumbing_org_id"])},
        )
        assert first_assign.status_code == 200, first_assign.text

        switch_demo_user(client, "triage@fixhub.test")
        triage_response = client.patch(f"/api/jobs/{job['id']}", json={"status": "triaged"})
        assert triage_response.status_code == 200, triage_response.text

        switch_demo_user(client, "coordinator@fixhub.test")
        reassign_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={"assigned_org_id": str(ids["campus_maintenance_org_id"])},
        )
        resident_view = client.get(f"/api/jobs/{job['id']}")
        events = job_events(client, job["id"])

    assert reassign_response.status_code == 200, reassign_response.text
    assert resident_view.status_code == 200
    assert resident_view.json()["status"] == "triaged"
    assert resident_view.json()["assigned_org_name"] == "Campus Maintenance"
    assert resident_view.json()["coordination_headline"] == (
        "Dispatch target updated without changing lifecycle state"
    )
    assert resident_view.json()["coordination_owner_label"] == "Dispatch coordinator"
    assert resident_view.json()["coordination_detail"] == "Reassigned Campus Maintenance"
    assert events[-1]["event_type"] == "assignment"
    assert events[-1]["target_status"] is None


def test_note_events_snapshot_current_assignment_context(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        switch_demo_user(client, "resident@fixhub.test")
        job = create_job(client, location_id=ids["room_a14_location_id"])

        switch_demo_user(client, "coordinator@fixhub.test")
        assign_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={"assigned_org_id": str(ids["newcastle_plumbing_org_id"])},
        )
        assert assign_response.status_code == 200, assign_response.text

        note_response = client.post(
            f"/api/jobs/{job['id']}/events",
            json={"message": "Contractor attendance window requested"},
        )

    assert note_response.status_code == 201
    assert note_response.json()["assigned_org_id"] == str(ids["newcastle_plumbing_org_id"])
    assert note_response.json()["assigned_org_name"] == "Newcastle Plumbing"
    assert note_response.json()["assigned_contractor_user_id"] is None


def test_contractor_visibility_uses_event_backed_assignment_when_job_row_drifts(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        switch_demo_user(client, "resident@fixhub.test")
        job = create_job(client, location_id=ids["room_a14_location_id"])

        switch_demo_user(client, "coordinator@fixhub.test")
        assign_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={"assigned_org_id": str(ids["newcastle_plumbing_org_id"])},
        )
        assert assign_response.status_code == 200, assign_response.text

        with app.state.SessionLocal() as session:
            drifted_job = session.get(Job, uuid.UUID(job["id"]))
            assert drifted_job is not None
            drifted_job.assigned_org_id = None
            drifted_job.assigned_contractor_user_id = None
            drifted_job.assigned_org = None
            drifted_job.assigned_contractor = None
            session.commit()

        switch_demo_user(client, "contractor@fixhub.test")
        contractor_job = client.get(f"/api/jobs/{job['id']}")
        contractor_list = client.get("/api/jobs")

    assert contractor_job.status_code == 200, contractor_job.text
    assert contractor_job.json()["assigned_org_name"] == "Newcastle Plumbing"
    assert contractor_list.status_code == 200, contractor_list.text
    assert [listed_job["id"] for listed_job in contractor_list.json()] == [job["id"]]


def test_reassigned_contractor_keeps_read_access_but_loses_write_access(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        switch_demo_user(client, "resident@fixhub.test")
        job = create_job(client, location_id=ids["room_a14_location_id"], title="Reassignment history access")

        switch_demo_user(client, "coordinator@fixhub.test")
        first_assign = client.patch(
            f"/api/jobs/{job['id']}",
            json={"assigned_org_id": str(ids["newcastle_plumbing_org_id"])},
        )
        assert first_assign.status_code == 200, first_assign.text

        switch_demo_user(client, "triage@fixhub.test")
        triage_response = client.patch(f"/api/jobs/{job['id']}", json={"status": "triaged"})
        assert triage_response.status_code == 200, triage_response.text

        switch_demo_user(client, "coordinator@fixhub.test")
        reassign_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={"assigned_org_id": str(ids["campus_maintenance_org_id"])},
        )
        assert reassign_response.status_code == 200, reassign_response.text

        switch_demo_user(client, "contractor@fixhub.test", next_path=f"/contractor/jobs/{job['id']}")
        contractor_job = client.get(f"/api/jobs/{job['id']}")
        contractor_visible_list = client.get("/api/jobs")
        contractor_assigned_list = client.get("/api/jobs", params={"assigned": "true"})
        progress_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={"status": "in_progress", "event_message": "Old contractor should not be able to restart work"},
        )
        note_response = client.post(
            f"/api/jobs/{job['id']}/events",
            json={"message": "Old contractor should not be able to add notes either"},
        )
        queue_page = client.get("/contractor/jobs")
        page = client.get(f"/contractor/jobs/{job['id']}")

    assert contractor_job.status_code == 200, contractor_job.text
    assert contractor_job.json()["assigned_org_name"] == "Campus Maintenance"
    assert contractor_visible_list.status_code == 200, contractor_visible_list.text
    assert [listed_job["id"] for listed_job in contractor_visible_list.json()] == [job["id"]]
    assert contractor_assigned_list.status_code == 200, contractor_assigned_list.text
    assert contractor_assigned_list.json() == []
    assert progress_response.status_code == 403
    assert progress_response.json() == {"detail": "Only the currently assigned contractor can update this job"}
    assert note_response.status_code == 403
    assert note_response.json() == {"detail": "Only the currently assigned contractor can update this job"}
    assert queue_page.status_code == 200
    assert "No jobs are currently dispatched to you." in queue_page.text
    assert "Reassignment history access" not in queue_page.text
    assert page.status_code == 200
    assert "Historical visibility only" in page.text
    assert "execution updates are locked" in page.text
    assert "Progress controls" not in page.text


def test_report_creation_emits_initial_event_target_status_and_status_cache(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        switch_demo_user(client, "resident@fixhub.test")
        job = create_job(client, location_id=ids["room_a14_location_id"])
        events = job_events(client, job["id"])
        fetched_job = client.get(f"/api/jobs/{job['id']}")

    assert fetched_job.status_code == 200
    assert len(events) == 1
    assert events[0]["event_type"] == "report_created"
    assert events[0]["target_status"] == "new"
    assert fetched_job.json()["status"] == "new"


def test_job_and_event_reads_keep_original_location_snapshot_after_location_rename(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        switch_demo_user(client, "resident@fixhub.test")
        job = create_job(client, location_id=ids["room_a14_location_id"])

        with app.state.SessionLocal() as session:
            location = session.get(Location, ids["room_a14_location_id"])
            assert location is not None
            location.name = "Block A Room 14 Renamed"
            session.commit()

        fetched_job = client.get(f"/api/jobs/{job['id']}")
        events = job_events(client, job["id"])

    assert fetched_job.status_code == 200
    assert fetched_job.json()["location"] == "Callaghan Campus > Block A > Block A Room 14"
    assert events[0]["location"] == "Callaghan Campus > Block A > Block A Room 14"


def test_assignment_from_new_emits_dispatch_audit_without_silent_lifecycle_change(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        switch_demo_user(client, "resident@fixhub.test")
        job = create_job(client, location_id=ids["room_a14_location_id"])

        switch_demo_user(client, "coordinator@fixhub.test")
        assign_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={"assigned_org_id": str(ids["newcastle_plumbing_org_id"])},
        )
        assert assign_response.status_code == 200, assign_response.text

        switch_demo_user(client, "resident@fixhub.test")
        events = job_events(client, job["id"])

    assert [event["message"] for event in events] == [
        "Report created",
        "Assigned Newcastle Plumbing",
    ]
    assert [event["target_status"] for event in events] == ["new", None]
    assert assign_response.json()["status"] == "new"


def test_operations_job_page_includes_assignment_controls_for_dispatch_roles(tmp_path) -> None:
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
    assert 'name="event_message"' in page.text
    assert 'name="reason_code"' in page.text
    assert 'name="responsibility_owner"' in page.text
    assert "Choosing a direct contractor keeps that contractor&#39;s organisation attached for accountable dispatch." in page.text
    assert "Current coordination" in page.text
    assert 'data-status="scheduled"' not in page.text


def test_resident_job_page_shows_projected_coordination_summary(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        switch_demo_user(client, "resident@fixhub.test")
        job = create_job(client, location_id=ids["room_a14_location_id"], title="Buzzing exhaust fan")

        switch_demo_user(client, "coordinator@fixhub.test")
        assign_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={"assigned_org_id": str(ids["newcastle_plumbing_org_id"])},
        )
        assert assign_response.status_code == 200, assign_response.text

        switch_demo_user(client, "resident@fixhub.test", next_path=f"/resident/jobs/{job['id']}")
        page = client.get(f"/resident/jobs/{job['id']}")

    assert page.status_code == 200
    assert "Current coordination" in page.text
    assert "Dispatch target updated without changing lifecycle state" in page.text
    assert "Dispatch coordinator" in page.text


def test_resident_page_prefers_assignment_handoff_over_generic_triage_echo(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        switch_demo_user(client, "resident@fixhub.test")
        job = create_job(client, location_id=ids["room_a14_location_id"], title="Loose towel rail")

        switch_demo_user(client, "coordinator@fixhub.test")
        assign_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={"assigned_org_id": str(ids["newcastle_plumbing_org_id"])},
        )
        assert assign_response.status_code == 200, assign_response.text

        switch_demo_user(client, "triage@fixhub.test")
        triage_response = client.patch(f"/api/jobs/{job['id']}", json={"status": "triaged"})
        assert triage_response.status_code == 200, triage_response.text

        job_read = client.get(f"/api/jobs/{job['id']}")
        switch_demo_user(client, "resident@fixhub.test", next_path=f"/resident/jobs/{job['id']}")
        page = client.get(f"/resident/jobs/{job['id']}")

    assert job_read.status_code == 200
    assert job_read.json()["latest_operations_update_message"] == "Assigned Newcastle Plumbing"
    assert page.status_code == 200
    assert "Assigned Newcastle Plumbing" in page.text
    assert "Triage review recorded" not in page.text


def test_resident_can_add_access_update_that_staff_can_see_on_job_page(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        switch_demo_user(client, "resident@fixhub.test")
        job = create_job(client, location_id=ids["room_a14_location_id"], title="Leaking shower mixer")
        resident_update = client.post(
            f"/api/jobs/{job['id']}/resident-update",
            json={
                "message": "I can give access after 3pm Tuesday and the room is occupied before then.",
                "reason_code": "resident_access_update",
            },
        )
        resident_page = client.get(f"/resident/jobs/{job['id']}")

        switch_demo_user(client, "triage@fixhub.test", next_path=f"/admin/jobs/{job['id']}")
        operations_page = client.get(f"/admin/jobs/{job['id']}")
        events = job_events(client, job["id"])

    assert resident_update.status_code == 201, resident_update.text
    assert resident_update.json()["reason_code"] == "resident_access_update"
    assert resident_update.json()["responsibility_stage"] == "coordination"
    assert resident_page.status_code == 200
    assert "Send resident update" in resident_page.text
    assert operations_page.status_code == 200
    assert "Resident sent an access update that operations need to apply" in operations_page.text
    assert "I can give access after 3pm Tuesday" in operations_page.text
    assert "Owner: Triage Officer" in operations_page.text
    assert events[-1]["actor_role"] == "resident"
    assert events[-1]["reason_code"] == "resident_access_update"
    assert events[-1]["responsibility_owner"] == "triage_officer"


def test_job_read_includes_latest_cross_role_updates(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        switch_demo_user(client, "resident@fixhub.test")
        job = create_job(client, location_id=ids["room_a14_location_id"], title="Shower pressure dropping")
        resident_update = client.post(
            f"/api/jobs/{job['id']}/resident-update",
            json={
                "message": "I can provide access after 4pm and the bathroom is free then.",
                "reason_code": "resident_access_update",
            },
        )
        assert resident_update.status_code == 201, resident_update.text

        switch_demo_user(client, "coordinator@fixhub.test")
        assign_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={"assigned_org_id": str(ids["newcastle_plumbing_org_id"])},
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
            json={"status": "scheduled", "event_message": "Booked plumber for Tuesday after the resident access window"},
        )
        assert schedule_response.status_code == 200, schedule_response.text

        switch_demo_user(client, "contractor@fixhub.test")
        progress_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={"status": "in_progress", "event_message": "Attended room, tested pressure, and isolated the failing mixer cartridge"},
        )
        assert progress_response.status_code == 200, progress_response.text

        job_read = client.get(f"/api/jobs/{job['id']}")

    assert job_read.status_code == 200
    payload = job_read.json()
    assert payload["latest_resident_update_message"] == "I can provide access after 4pm and the bathroom is free then."
    assert payload["latest_resident_update_actor_label"] == "Riley Resident (Student Living)"
    assert payload["latest_operations_update_message"] == "Booked plumber for Tuesday after the resident access window"
    assert payload["latest_operations_update_actor_label"] == "Priya Property Manager (Student Living)"
    assert payload["latest_contractor_update_message"] == "Attended room, tested pressure, and isolated the failing mixer cartridge"
    assert payload["latest_contractor_update_actor_label"] == "Devon Contractor (Newcastle Plumbing)"


def test_job_read_includes_action_required_projection(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        switch_demo_user(client, "resident@fixhub.test")
        job = create_job(client, location_id=ids["room_a14_location_id"], title="Tap booking needed")

        switch_demo_user(client, "coordinator@fixhub.test")
        assign_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={"assigned_org_id": str(ids["newcastle_plumbing_org_id"])},
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
            json={"status": "scheduled", "event_message": "Booked plumber for Friday afternoon after resident access confirmation"},
        )
        assert schedule_response.status_code == 200, schedule_response.text

        job_read = client.get(f"/api/jobs/{job['id']}")

    assert job_read.status_code == 200
    payload = job_read.json()
    assert payload["action_required_by"] == "Newcastle Plumbing"
    assert payload["action_required_summary"] == (
        "Attend the booked window and record whether work started, was blocked, or was completed."
    )


def test_demo_seed_data_includes_live_pilot_backlog(tmp_path) -> None:
    _, client = build_client(tmp_path)

    with client:
        switch_demo_user(client, "coordinator@fixhub.test", next_path="/admin/jobs")
        jobs_response = client.get("/api/jobs")
        admin_page = client.get("/admin/jobs")

    assert jobs_response.status_code == 200
    jobs = jobs_response.json()
    titles = {job["title"] for job in jobs}
    assert {
        "Shower mixer leaking again",
        "Laundry pump failing again",
        "Common room heater tripping overnight",
    }.issubset(titles)

    laundry_job = next(job for job in jobs if job["title"] == "Laundry pump failing again")
    heater_job = next(job for job in jobs if job["title"] == "Common room heater tripping overnight")

    assert laundry_job["status"] == "on_hold"
    assert laundry_job["coordination_headline"] == "Job on hold pending further action"
    assert laundry_job["action_required_summary"] == (
        "Record the condition needed to bring the job back into triage or scheduling."
    )
    assert heater_job["coordination_headline"] == "Resident says the issue is still active after completion"

    assert admin_page.status_code == 200
    assert "Action needed now" in admin_page.text
    assert "Laundry pump failing again" in admin_page.text


def test_cross_role_update_panels_surface_latest_handoffs_on_job_pages(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        switch_demo_user(client, "resident@fixhub.test")
        job = create_job(client, location_id=ids["room_a14_location_id"], title="Bathroom light flickering")
        resident_update = client.post(
            f"/api/jobs/{job['id']}/resident-update",
            json={
                "message": "Please avoid 9-11am because the room is occupied for an exam support session.",
                "reason_code": "resident_access_update",
            },
        )
        assert resident_update.status_code == 201, resident_update.text

        switch_demo_user(client, "coordinator@fixhub.test")
        assign_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={"assigned_org_id": str(ids["campus_maintenance_org_id"])},
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
            json={"status": "scheduled", "event_message": "Booked campus maintenance for the afternoon attendance window"},
        )
        assert schedule_response.status_code == 200, schedule_response.text

        switch_demo_user(client, "maintenance.contractor@fixhub.test")
        progress_response = client.patch(
            f"/api/jobs/{job['id']}",
            json={"status": "in_progress", "event_message": "On site now, checking the fitting and confirming the replacement lamp stock"},
        )
        assert progress_response.status_code == 200, progress_response.text
        contractor_page = client.get(f"/contractor/jobs/{job['id']}")

        switch_demo_user(client, "triage@fixhub.test")
        operations_page = client.get(f"/admin/jobs/{job['id']}")

        switch_demo_user(client, "resident@fixhub.test")
        resident_page = client.get(f"/resident/jobs/{job['id']}")

    assert resident_page.status_code == 200
    assert "Latest team updates" in resident_page.text
    assert "Booked campus maintenance for the afternoon attendance window" in resident_page.text
    assert "On site now, checking the fitting and confirming the replacement lamp stock" in resident_page.text

    assert operations_page.status_code == 200
    assert "Cross-role updates" in operations_page.text
    assert "Please avoid 9-11am because the room is occupied for an exam support session." in operations_page.text
    assert "On site now, checking the fitting and confirming the replacement lamp stock" in operations_page.text

    assert contractor_page.status_code == 200
    assert "Latest handoff context" in contractor_page.text
    assert "Booked campus maintenance for the afternoon attendance window" in contractor_page.text
    assert "Please avoid 9-11am because the room is occupied for an exam support session." in contractor_page.text


def test_job_pages_surface_repeat_history_for_same_location(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        switch_demo_user(client, "resident@fixhub.test")
        earlier_job = create_job(client, location_id=ids["room_a14_location_id"], title="Earlier sink leak")
        complete_org_assigned_job(client, earlier_job["id"], assigned_org_id=ids["newcastle_plumbing_org_id"])

        current_job = create_job(client, location_id=ids["room_a14_location_id"], title="Leak returned after last visit")

        switch_demo_user(client, "coordinator@fixhub.test")
        assign_response = client.patch(
            f"/api/jobs/{current_job['id']}",
            json={"assigned_org_id": str(ids["newcastle_plumbing_org_id"])},
        )
        assert assign_response.status_code == 200, assign_response.text

        switch_demo_user(client, "triage@fixhub.test")
        triage_response = client.patch(f"/api/jobs/{current_job['id']}", json={"status": "triaged"})
        assert triage_response.status_code == 200, triage_response.text

        schedule_response = client.patch(
            f"/api/jobs/{current_job['id']}",
            json={"status": "scheduled", "event_message": "Booked plumber after repeat leak report"},
        )
        assert schedule_response.status_code == 200, schedule_response.text

        switch_demo_user(client, "resident@fixhub.test", next_path=f"/resident/jobs/{current_job['id']}")
        resident_page = client.get(f"/resident/jobs/{current_job['id']}")

        switch_demo_user(client, "triage@fixhub.test", next_path=f"/admin/jobs/{current_job['id']}")
        operations_page = client.get(f"/admin/jobs/{current_job['id']}")

        switch_demo_user(client, "contractor@fixhub.test", next_path=f"/contractor/jobs/{current_job['id']}")
        contractor_page = client.get(f"/contractor/jobs/{current_job['id']}")

    assert resident_page.status_code == 200
    assert "Earlier reports here" in resident_page.text
    assert "Earlier sink leak" in resident_page.text
    assert "Work marked complete" in resident_page.text

    assert operations_page.status_code == 200
    assert "Repeat history at this location" in operations_page.text
    assert "Earlier sink leak" in operations_page.text
    assert "Work marked complete" in operations_page.text

    assert contractor_page.status_code == 200
    assert "Earlier visible jobs here" in contractor_page.text
    assert "Earlier sink leak" in contractor_page.text
    assert "Work marked complete" in contractor_page.text


def test_response_needed_signal_tracks_newer_cross_role_updates(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        switch_demo_user(client, "resident@fixhub.test")
        resident_job = create_job(client, location_id=ids["room_a14_location_id"], title="Shower access changed")

        switch_demo_user(client, "coordinator@fixhub.test")
        assign_response = client.patch(
            f"/api/jobs/{resident_job['id']}",
            json={"assigned_org_id": str(ids["campus_maintenance_org_id"])},
        )
        assert assign_response.status_code == 200, assign_response.text

        switch_demo_user(client, "triage@fixhub.test")
        triage_response = client.patch(f"/api/jobs/{resident_job['id']}", json={"status": "triaged"})
        assert triage_response.status_code == 200, triage_response.text
        schedule_response = client.patch(
            f"/api/jobs/{resident_job['id']}",
            json={"status": "scheduled", "event_message": "Booked maintenance for Wednesday afternoon"},
        )
        assert schedule_response.status_code == 200, schedule_response.text

        switch_demo_user(client, "resident@fixhub.test")
        resident_update = client.post(
            f"/api/jobs/{resident_job['id']}/resident-update",
            json={
                "message": "Please avoid 1-2pm because the room is locked for a welfare check.",
                "reason_code": "resident_access_update",
            },
        )
        assert resident_update.status_code == 201, resident_update.text

        switch_demo_user(client, "triage@fixhub.test")
        resident_job_read = client.get(f"/api/jobs/{resident_job['id']}")
        admin_queue = client.get("/admin/jobs")
        contractor_detail = None

        switch_demo_user(client, "maintenance.contractor@fixhub.test", next_path=f"/contractor/jobs/{resident_job['id']}")
        contractor_detail = client.get(f"/contractor/jobs/{resident_job['id']}")

        switch_demo_user(client, "resident@fixhub.test")
        contractor_job = create_job(client, location_id=ids["room_a14_location_id"], title="Blocked plumbing visit")
        move_to_in_progress(client, contractor_job["id"], assigned_org_id=ids["newcastle_plumbing_org_id"])

        blocked_response = client.patch(
            f"/api/jobs/{contractor_job['id']}",
            json={
                "status": "blocked",
                "reason_code": "no_access",
                "event_message": "Arrived on site but front desk had no master key available for the room.",
            },
        )
        assert blocked_response.status_code == 200, blocked_response.text

        admin_blocked_read = client.get(f"/api/jobs/{contractor_job['id']}")
        blocked_queue = client.get("/admin/jobs")

    assert resident_job_read.status_code == 200
    resident_payload = resident_job_read.json()
    assert resident_payload["pending_signal_headline"] == "Resident access detail needs operations follow-through"
    assert resident_payload["pending_signal_summary"] == (
        "Apply the resident note to scheduling, dispatch, or follow-up before the next visit."
    )
    assert resident_payload["pending_signal_actor_label"] == "Riley Resident (Student Living)"

    assert admin_queue.status_code == 200
    assert "Response-needed signal: Resident access detail needs operations follow-through" in admin_queue.text
    assert "Please avoid 1-2pm because the room is locked for a welfare check." in contractor_detail.text
    assert "Response-needed signal" in contractor_detail.text
    assert "Resident access detail needs operations follow-through" in contractor_detail.text

    assert admin_blocked_read.status_code == 200
    blocked_payload = admin_blocked_read.json()
    assert blocked_payload["pending_signal_headline"] == "Field blocker needs coordination"
    assert blocked_payload["pending_signal_summary"] == (
        "Review the field update and record the rebooking, access, or escalation path."
    )
    assert blocked_payload["pending_signal_actor_label"] == "Devon Contractor (Newcastle Plumbing)"

    assert blocked_queue.status_code == 200
    assert "Response-needed signal: Field blocker needs coordination" in blocked_queue.text


def test_completed_job_surfaces_resident_recurrence_without_fake_status_change(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        switch_demo_user(client, "resident@fixhub.test")
        job = create_job(client, location_id=ids["room_a14_location_id"], title="Tap still leaking")
        complete_org_assigned_job(client, job["id"], assigned_org_id=ids["newcastle_plumbing_org_id"])

        switch_demo_user(client, "resident@fixhub.test")
        recurrence_response = client.post(
            f"/api/jobs/{job['id']}/resident-update",
            json={
                "message": "The leak started again this morning after yesterday's completion.",
                "reason_code": "issue_still_present",
            },
        )
        resident_job = client.get(f"/api/jobs/{job['id']}")
        resident_page = client.get(f"/resident/jobs/{job['id']}")

        switch_demo_user(client, "triage@fixhub.test", next_path=f"/admin/jobs/{job['id']}")
        operations_page = client.get(f"/admin/jobs/{job['id']}")
        events = job_events(client, job["id"])

    assert recurrence_response.status_code == 201, recurrence_response.text
    assert resident_job.status_code == 200
    assert resident_job.json()["status"] == "completed"
    assert resident_job.json()["coordination_headline"] == "Resident says the issue is still active after completion"
    assert resident_job.json()["coordination_owner_label"] == "Property manager"
    assert resident_job.json()["latest_event_actor_label"].startswith("Riley Resident")
    assert resident_page.status_code == 200
    assert "Resident says the issue is still active after completion" in resident_page.text
    assert operations_page.status_code == 200
    assert "Updated " in operations_page.text
    assert events[-1]["target_status"] is None
    assert events[-1]["reason_code"] == "issue_still_present"


def test_non_residents_cannot_use_resident_update_endpoint(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        switch_demo_user(client, "resident@fixhub.test")
        job = create_job(client, location_id=ids["room_a14_location_id"])

        switch_demo_user(client, "triage@fixhub.test")
        response = client.post(
            f"/api/jobs/{job['id']}/resident-update",
            json={"message": "Not actually a resident update"},
        )

    assert response.status_code == 403
    assert response.json() == {"detail": "Only residents can add resident updates"}


def test_operations_pages_hide_controls_by_role(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        switch_demo_user(client, "resident@fixhub.test")
        job = create_job(client, location_id=ids["room_a14_location_id"], title="Access query")

        switch_demo_user(client, "reception@fixhub.test", next_path=f"/admin/jobs/{job['id']}")
        reception_page = client.get(f"/admin/jobs/{job['id']}")

        switch_demo_user(client, "triage@fixhub.test", next_path=f"/admin/jobs/{job['id']}")
        triage_page = client.get(f"/admin/jobs/{job['id']}")

    assert reception_page.status_code == 200
    assert 'name="assigned_org_id"' not in reception_page.text
    assert 'data-status="triaged"' not in reception_page.text
    assert "Add event" in reception_page.text

    assert triage_page.status_code == 200
    assert 'name="assigned_org_id"' not in triage_page.text
    assert 'data-status="triaged"' in triage_page.text
    assert 'data-status="scheduled"' not in triage_page.text
    assert 'data-status="on_hold"' in triage_page.text
    assert 'data-status="escalated"' not in triage_page.text
    assert 'data-status="follow_up_scheduled"' not in triage_page.text
    assert 'data-status="reopened"' not in triage_page.text


def test_contractor_job_page_hides_on_hold_control(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        switch_demo_user(client, "resident@fixhub.test")
        job = create_job(client, location_id=ids["room_a14_location_id"])
        move_to_in_progress(client, job["id"], assigned_org_id=ids["newcastle_plumbing_org_id"])

        switch_demo_user(client, "contractor@fixhub.test", next_path=f"/contractor/jobs/{job['id']}")
        page = client.get(f"/contractor/jobs/{job['id']}")

    assert page.status_code == 200
    assert 'data-status="blocked"' in page.text
    assert 'data-status="completed"' in page.text
    assert 'data-status="in_progress"' not in page.text
    assert 'data-status="on_hold"' not in page.text
    assert 'name="event_message"' in page.text
    assert 'name="reason_code"' in page.text
    assert 'name="responsibility_owner"' in page.text


def test_operations_page_only_shows_follow_up_or_reopen_when_job_state_allows_it(tmp_path) -> None:
    app, client = build_client(tmp_path)

    with client:
        ids = lookup_ids(app)
        switch_demo_user(client, "resident@fixhub.test")
        job = create_job(client, location_id=ids["room_a14_location_id"], title="Recurring leak review")
        complete_org_assigned_job(client, job["id"], assigned_org_id=ids["newcastle_plumbing_org_id"])

        switch_demo_user(client, "triage@fixhub.test", next_path=f"/admin/jobs/{job['id']}")
        triage_page = client.get(f"/admin/jobs/{job['id']}")

        switch_demo_user(client, "coordinator@fixhub.test", next_path=f"/admin/jobs/{job['id']}")
        coordinator_page = client.get(f"/admin/jobs/{job['id']}")

    assert triage_page.status_code == 200
    assert 'data-status="follow_up_scheduled"' in triage_page.text
    assert 'data-status="reopened"' not in triage_page.text
    assert 'data-status="scheduled"' not in triage_page.text

    assert coordinator_page.status_code == 200
    assert 'data-status="reopened"' in coordinator_page.text
    assert 'data-status="follow_up_scheduled"' not in coordinator_page.text
    assert 'data-status="escalated"' not in coordinator_page.text
