from __future__ import annotations

import uuid
from datetime import datetime

from app.models import OrganisationType, UserRole
from app.schema.base import SchemaModel


class UserRead(SchemaModel):
    id: uuid.UUID
    name: str
    email: str
    role: UserRole
    organisation_id: uuid.UUID | None = None
    organisation_name: str | None = None
    organisation_type: OrganisationType | None = None
    created_at: datetime
