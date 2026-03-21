from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Asset, Location, LocationType, User
from app.schema import AssetOption, LocationOption


REPORTABLE_LOCATION_TYPES = (LocationType.space, LocationType.unit)


def find_or_create_asset(session: Session, *, location: Location, name: str) -> Asset:
    asset = session.scalar(
        select(Asset)
        .where(Asset.location_id == location.id, Asset.name == name)
        .limit(1)
    )
    if asset is None:
        asset = Asset(location_id=location.id, name=name)
        session.add(asset)
        session.flush()
    return asset


def build_location_asset_catalog(session: Session, *, user: User) -> list[dict[str, object]]:
    if user.organisation_id is None:
        return []

    locations = list(
        session.scalars(
            select(Location)
            .where(
                Location.organisation_id == user.organisation_id,
                Location.type.in_(REPORTABLE_LOCATION_TYPES),
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
            type=location.type,
            assets=[
                AssetOption(id=asset.id, name=asset.name)
                for asset in location.assets
            ],
        ).model_dump(mode="json")
        for location in locations
    ]


def is_reportable_location(location: Location) -> bool:
    return location.type in REPORTABLE_LOCATION_TYPES
