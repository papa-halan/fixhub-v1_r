from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import ValidationInfo, field_validator

from app.models import UserRole
from app.schema.base import SchemaModel, strip_non_blank


class EventCreate(SchemaModel):
    message: str

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str, info: ValidationInfo) -> str:
        return strip_non_blank(value, info.field_name)


class EventRead(SchemaModel):
    id: uuid.UUID
    job_id: uuid.UUID
    location_id: uuid.UUID | None = None
    location: str | None = None
    asset_id: uuid.UUID | None = None
    asset_name: str | None = None
    actor_user_id: uuid.UUID | None = None
    actor_org_id: uuid.UUID | None = None
    actor_name: str
    actor_role: UserRole | None = None
    actor_role_label: str | None = None
    organisation_name: str | None = None
    actor_label: str
    message: str
    created_at: datetime
