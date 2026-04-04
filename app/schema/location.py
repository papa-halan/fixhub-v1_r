from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from app.models import LocationType
from app.schema.asset import AssetOption
from app.schema.base import SchemaModel


class LocationRead(SchemaModel):
    id: uuid.UUID
    organisation_id: uuid.UUID
    parent_id: uuid.UUID | None = None
    name: str
    type: LocationType
    created_at: datetime


class LocationOption(SchemaModel):
    id: uuid.UUID
    parent_id: uuid.UUID | None = None
    name: str
    label: str
    type: LocationType
    assets: list[AssetOption] = Field(default_factory=list)
