from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from app.schema.asset import AssetOption
from app.schema.base import SchemaModel


class LocationRead(SchemaModel):
    id: uuid.UUID
    organisation_id: uuid.UUID
    name: str
    created_at: datetime


class LocationOption(SchemaModel):
    id: uuid.UUID
    name: str
    assets: list[AssetOption] = Field(default_factory=list)
