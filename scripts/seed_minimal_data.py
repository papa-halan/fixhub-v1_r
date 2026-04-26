from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.database import build_engine, build_session_factory, require_schema_ready, resolve_database_url
from app.models import UserRole
from app.services import MinimalSeedConfig, ensure_minimal_seed_data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a minimal non-demo FixHub dataset for local API testing.",
    )
    parser.add_argument("--database-url", default=None, help="Database URL to seed. Defaults to DATABASE_URL.")
    parser.add_argument("--organisation-name", default="Student Living")
    parser.add_argument("--site-name", default="Callaghan Campus")
    parser.add_argument("--building-name", default="Block A")
    parser.add_argument("--unit-name", default="Block A Room 14")
    parser.add_argument("--shared-space-name", default="Block A Common Room")
    parser.add_argument("--skip-shared-space", action="store_true", help="Do not create a sibling shared space.")
    parser.add_argument("--asset-name", default="Sink")
    parser.add_argument("--skip-asset", action="store_true", help="Do not create a default asset on the unit.")
    parser.add_argument("--operator-name", default="FixHub Admin")
    parser.add_argument("--operator-email", default="ops@fixhub.local")
    parser.add_argument("--operator-password", default="fixhub-admin-password")
    parser.add_argument(
        "--operator-role",
        choices=[
            UserRole.admin.value,
            UserRole.reception_admin.value,
            UserRole.triage_officer.value,
            UserRole.coordinator.value,
        ],
        default=UserRole.admin.value,
    )
    parser.add_argument("--resident-name", default="Test Resident")
    parser.add_argument("--resident-email", default="resident@fixhub.local")
    parser.add_argument("--resident-password", default="fixhub-resident-password")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    database_url = resolve_database_url(args.database_url)
    engine = build_engine(database_url)
    session_factory = build_session_factory(engine)

    try:
        require_schema_ready(engine)
        with session_factory() as session:
            summary = ensure_minimal_seed_data(
                session,
                config=MinimalSeedConfig(
                    organisation_name=args.organisation_name,
                    site_name=args.site_name,
                    building_name=args.building_name,
                    unit_name=args.unit_name,
                    shared_space_name=None if args.skip_shared_space else args.shared_space_name,
                    asset_name=None if args.skip_asset else args.asset_name,
                    operator_name=args.operator_name,
                    operator_email=args.operator_email,
                    operator_password=args.operator_password,
                    operator_role=UserRole(args.operator_role),
                    resident_name=args.resident_name,
                    resident_email=args.resident_email,
                    resident_password=args.resident_password,
                ),
            )
            session.commit()
    finally:
        engine.dispose()

    print(
        json.dumps(
            {
                "database_url": database_url,
                "organisation": {"id": str(summary.organisation_id), "name": args.organisation_name},
                "location": {
                    "site_id": str(summary.site_id),
                    "building_id": str(summary.building_id),
                    "unit_id": str(summary.unit_id),
                    "unit_label": summary.unit_label,
                },
                "shared_space": (
                    {"id": str(summary.shared_space_id), "label": summary.shared_space_label}
                    if summary.shared_space_id is not None
                    else None
                ),
                "asset": (
                    {"id": str(summary.asset_id), "name": summary.asset_name}
                    if summary.asset_id is not None
                    else None
                ),
                "users": {
                    "operator": {
                        "id": str(summary.operator_user_id),
                        "email": summary.operator_email,
                        "role": summary.operator_role.value,
                    },
                    "resident": {
                        "id": str(summary.resident_user_id),
                        "email": summary.resident_email,
                    },
                },
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
