from __future__ import annotations

import uuid
from datetime import datetime

from app.schema.base import SchemaModel


class AssetRead(SchemaModel):
    id: uuid.UUID
    location_id: uuid.UUID
    name: str
    created_at: datetime


class AssetOption(SchemaModel):
    id: uuid.UUID
    name: str
