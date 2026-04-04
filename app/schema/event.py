from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import ValidationInfo, field_validator

from app.models import (
    EventType,
    JobStatus,
    OwnerScope,
    ResidentUpdateReason,
    ResponsibilityOwner,
    ResponsibilityStage,
    UserRole,
)
from app.schema.base import SchemaModel, strip_non_blank


class EventCreate(SchemaModel):
    message: str
    reason_code: str | None = None
    responsibility_stage: ResponsibilityStage | None = None
    owner_scope: OwnerScope | None = None
    responsibility_owner: ResponsibilityOwner | None = None

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str, info: ValidationInfo) -> str:
        return strip_non_blank(value, info.field_name)

    @field_validator("reason_code")
    @classmethod
    def validate_reason_code(cls, value: str | None, info: ValidationInfo) -> str | None:
        if value is None:
            return None
        return strip_non_blank(value, info.field_name)


class ResidentUpdateCreate(SchemaModel):
    message: str
    reason_code: ResidentUpdateReason

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
    assigned_org_id: uuid.UUID | None = None
    assigned_org_name: str | None = None
    assigned_contractor_user_id: uuid.UUID | None = None
    assigned_contractor_name: str | None = None
    actor_label: str
    event_type: EventType
    target_status: JobStatus | None = None
    message: str
    reason_code: str | None = None
    responsibility_stage: ResponsibilityStage | None = None
    owner_scope: OwnerScope | None = None
    responsibility_owner: ResponsibilityOwner | None = None
    created_at: datetime
