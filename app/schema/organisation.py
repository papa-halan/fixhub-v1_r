from __future__ import annotations

import uuid
from datetime import datetime

from app.models import ContractorMode, OrganisationType
from app.schema.base import SchemaModel


class OrganisationRead(SchemaModel):
    id: uuid.UUID
    name: str
    type: OrganisationType
    parent_org_id: uuid.UUID | None = None
    contractor_mode: ContractorMode | None = None
    created_at: datetime


class OrganisationOption(SchemaModel):
    id: uuid.UUID
    name: str
