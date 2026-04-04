from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Asset, Location, LocationType, User
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


def build_location_asset_catalog(session: Session, *, user: User) -> list[dict[str, object]]:
    if user.organisation_id is None:
        return []

    locations = list(
        session.scalars(
            select(Location)
            .where(
                Location.organisation_id == user.organisation_id,
                Location.type.in_(REPORTABLE_LOCATION_TYPES),
                Location.parent_id.is_not(None),
            )
            .options(selectinload(Location.assets))
            .order_by(Location.name.asc())
        )
    )

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
        for location in locations
    ]


def is_reportable_location(location: Location) -> bool:
    return location.type in REPORTABLE_LOCATION_TYPES and location.parent_id is not None
