from __future__ import annotations

import uuid
from datetime import datetime

from app.models import OrganisationType
from app.schema.base import SchemaModel


class OrganisationRead(SchemaModel):
    id: uuid.UUID
    name: str
    type: OrganisationType
    created_at: datetime


class OrganisationOption(SchemaModel):
    id: uuid.UUID
    name: str
