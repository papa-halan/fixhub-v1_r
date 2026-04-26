from __future__ import annotations

from sqlalchemy import select

from app.main import create_app
from app.models import User
from app.services import MinimalSeedConfig, build_location_asset_catalog, ensure_minimal_seed_data
from tests.support import build_settings, migrate_to_head, sqlite_database_url


def test_minimal_seed_data_includes_shared_space_in_resident_catalog(tmp_path) -> None:
    database_url = sqlite_database_url(tmp_path / "fixhub.db")
    migrate_to_head(database_url)

    app = create_app(
        settings_override=build_settings(
            database_url,
            demo_mode=False,
            seed_demo_data=False,
        )
    )

    try:
        with app.state.SessionLocal() as session:
            summary = ensure_minimal_seed_data(session, config=MinimalSeedConfig())
            session.commit()

            resident = session.scalar(select(User).where(User.email == summary.resident_email).limit(1))
            assert resident is not None

            catalog = build_location_asset_catalog(session, user=resident)

        labels = {location["label"] for location in catalog}
        assert labels == {
            summary.unit_label,
            summary.shared_space_label,
        }
    finally:
        app.state.engine.dispose()
