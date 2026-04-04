from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Asset, Location, LocationType, User, UserRole
from app.schema import AssetOption, LocationOption


REPORTABLE_LOCATION_TYPES = (LocationType.space, LocationType.unit)


def location_lineage(location: Location) -> list[Location]:
    lineage: list[Location] = []
    seen_ids: set[object] = set()
    current: Location | None = location

    while current is not None and current.id not in seen_ids:
        lineage.append(current)
        seen_ids.add(current.id)
        current = current.parent

    return list(reversed(lineage))


def location_label(location: Location) -> str:
    return " > ".join(node.name for node in location_lineage(location))


def find_asset_by_name(session: Session, *, location: Location, name: str) -> Asset | None:
    return session.scalar(
        select(Asset)
        .where(Asset.location_id == location.id, Asset.name == name)
        .limit(1)
    )


def _reportable_locations_stmt(*, organisation_id) -> object:
    return (
        select(Location)
        .where(
            Location.organisation_id == organisation_id,
            Location.type.in_(REPORTABLE_LOCATION_TYPES),
            Location.parent_id.is_not(None),
        )
        .options(selectinload(Location.assets))
        .order_by(Location.name.asc())
    )


def _resident_scope_allows_location(home_location: Location, candidate: Location) -> bool:
    if candidate.id == home_location.id:
        return True

    if home_location.type == LocationType.unit:
        return candidate.parent_id == home_location.parent_id and candidate.type == LocationType.space

    return False


def reportable_locations_for_user(session: Session, *, user: User) -> list[Location]:
    if user.organisation_id is None:
        return []

    locations = list(session.scalars(_reportable_locations_stmt(organisation_id=user.organisation_id)))
    if user.role != UserRole.resident:
        return locations

    home_location = user.home_location
    if home_location is None:
        return locations

    return [location for location in locations if _resident_scope_allows_location(home_location, location)]


def can_user_report_location(session: Session, *, user: User, location: Location) -> bool:
    return any(candidate.id == location.id for candidate in reportable_locations_for_user(session, user=user))


def build_location_asset_catalog(session: Session, *, user: User) -> list[dict[str, object]]:
    return [
        LocationOption(
            id=location.id,
            parent_id=location.parent_id,
            name=location.name,
            label=location_label(location),
            type=location.type,
            assets=[
                AssetOption(id=asset.id, name=asset.name)
                for asset in location.assets
            ],
        ).model_dump(mode="json")
        for location in reportable_locations_for_user(session, user=user)
    ]


def is_reportable_location(location: Location) -> bool:
    return location.type in REPORTABLE_LOCATION_TYPES and location.parent_id is not None
