from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Asset, Location, User
from app.schema import AssetOption, LocationOption


def find_or_create_location(session: Session, *, user: User, name: str) -> Location:
    location = session.scalar(
        select(Location)
        .where(Location.user_id == user.id, Location.name == name)
        .limit(1)
    )
    if location is None:
        location = Location(user_id=user.id, name=name)
        session.add(location)
        session.flush()
    return location


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
    locations = list(
        session.scalars(
            select(Location)
            .where(Location.user_id == user.id)
            .options(selectinload(Location.assets))
            .order_by(Location.name.asc())
        )
    )

    return [
        LocationOption(
            id=location.id,
            name=location.name,
            assets=[
                AssetOption(id=asset.id, name=asset.name)
                for asset in location.assets
            ],
        ).model_dump(mode="json")
        for location in locations
    ]
