from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from tests.support import build_settings, migrate_to_head, sqlite_database_url


ROOT_DIR = Path(__file__).resolve().parents[1]


def test_app_releases_sqlite_file_on_shutdown(tmp_path) -> None:
    database_path = tmp_path / "fixhub.db"
    database_url = sqlite_database_url(database_path)
    migrate_to_head(database_url)

    settings = build_settings(
        database_url,
        demo_mode=False,
        seed_demo_data=False,
        bootstrap_user_email="ops.release@fixhub.local",
        bootstrap_user_password="fixhub-release-password",
    )

    with TestClient(create_app(settings_override=settings)) as client:
        response = client.get("/")
        assert response.status_code == 200

    database_path.unlink()
    assert not database_path.exists()


def test_manual_seed_script_supports_login_create_job_and_add_event(tmp_path) -> None:
    database_url = sqlite_database_url(tmp_path / "fixhub.db")
    migrate_to_head(database_url)

    operator_password = "fixhub-ops-password"
    resident_password = "fixhub-resident-password"
    command = [
        sys.executable,
        str(ROOT_DIR / "scripts" / "seed_minimal_data.py"),
        "--database-url",
        database_url,
        "--operator-password",
        operator_password,
        "--resident-password",
        resident_password,
    ]
    result = subprocess.run(
        command,
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        check=True,
    )
    summary = json.loads(result.stdout)
    assert summary["shared_space"]["label"] == "Callaghan Campus > Block A > Block A Common Room"

    settings = build_settings(
        database_url,
        demo_mode=False,
        seed_demo_data=False,
    )

    with TestClient(create_app(settings_override=settings)) as client:
        switcher_response = client.get("/switch-user", params={"email": summary["users"]["resident"]["email"]})
        assert switcher_response.status_code == 404

        resident_login = client.post(
            "/login",
            json={
                "email": summary["users"]["resident"]["email"],
                "password": resident_password,
            },
        )
        assert resident_login.status_code == 200
        assert resident_login.json()["redirect_path"] == "/resident/report"

        create_job_response = client.post(
            "/api/jobs",
            json={
                "title": "Leaking sink",
                "description": "Water is pooling under the vanity.",
                "location_id": summary["location"]["unit_id"],
                "asset_name": summary["asset"]["name"],
                "location_detail_text": "Inside the ensuite under the basin",
            },
        )
        assert create_job_response.status_code == 201, create_job_response.text
        job = create_job_response.json()
        assert job["location_id"] == summary["location"]["unit_id"]
        assert job["asset_name"] == summary["asset"]["name"]

        logout_response = client.post("/logout", follow_redirects=False)
        assert logout_response.status_code == 303

        operator_login = client.post(
            "/login",
            json={
                "email": summary["users"]["operator"]["email"],
                "password": operator_password,
            },
        )
        assert operator_login.status_code == 200
        assert operator_login.json()["redirect_path"] == "/admin/jobs"

        add_event_response = client.post(
            f"/api/jobs/{job['id']}/events",
            json={"message": "Front desk acknowledged the report and queued it for triage."},
        )
        assert add_event_response.status_code == 201, add_event_response.text

        events_response = client.get(f"/api/jobs/{job['id']}/events")
        assert events_response.status_code == 200
        events = events_response.json()

    assert [event["event_type"] for event in events] == ["report_created", "note"]
    assert events[0]["message"] == "Resident reported the issue through the portal."
    assert events[1]["message"] == "Front desk acknowledged the report and queued it for triage."
