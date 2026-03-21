from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import ValidationInfo, field_validator

from app.models import JobStatus, OwnerScope, ResponsibilityStage
from app.schema.base import SchemaModel, strip_non_blank


class JobCreate(SchemaModel):
    title: str
    description: str
    location_id: uuid.UUID
    location_detail_text: str | None = None
    asset_name: str | None = None

    @field_validator("title", "description")
    @classmethod
    def validate_text(cls, value: str, info: ValidationInfo) -> str:
        return strip_non_blank(value, info.field_name)

    @field_validator("location_detail_text")
    @classmethod
    def validate_location_detail_text(cls, value: str | None, info: ValidationInfo) -> str | None:
        if value is None:
            return None
        return strip_non_blank(value, info.field_name)

    @field_validator("asset_name")
    @classmethod
    def validate_asset_name(cls, value: str | None, info: ValidationInfo) -> str | None:
        if value is None:
            return None
        return strip_non_blank(value, info.field_name)


class JobUpdate(SchemaModel):
    assigned_org_id: uuid.UUID | None = None
    assigned_contractor_user_id: uuid.UUID | None = None
    status: JobStatus | None = None
    reason_code: str | None = None
    responsibility_stage: ResponsibilityStage | None = None
    owner_scope: OwnerScope | None = None

    @field_validator("reason_code")
    @classmethod
    def validate_reason_code(cls, value: str | None, info: ValidationInfo) -> str | None:
        if value is None:
            return None
        return strip_non_blank(value, info.field_name)


class JobRead(SchemaModel):
    id: uuid.UUID
    title: str
    description: str
    organisation_id: uuid.UUID
    location: str
    location_id: uuid.UUID
    location_detail_text: str | None = None
    asset_id: uuid.UUID | None = None
    asset_name: str | None = None
    status: JobStatus
    status_label: str
    created_by: uuid.UUID
    created_by_name: str
    assigned_org_id: uuid.UUID | None = None
    assigned_org_name: str | None = None
    assigned_contractor_user_id: uuid.UUID | None = None
    assigned_contractor_name: str | None = None
    assignee_scope: OwnerScope | None = None
    assignee_label: str | None = None
    created_at: datetime
    updated_at: datetime
