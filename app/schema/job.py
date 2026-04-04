from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import ValidationInfo, field_validator

from app.models import EventType, JobStatus, OwnerScope, ResponsibilityOwner, ResponsibilityStage
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
    event_message: str | None = None
    reason_code: str | None = None
    responsibility_stage: ResponsibilityStage | None = None
    owner_scope: OwnerScope | None = None
    responsibility_owner: ResponsibilityOwner | None = None

    @field_validator("event_message")
    @classmethod
    def validate_event_message(cls, value: str | None, info: ValidationInfo) -> str | None:
        if value is None:
            return None
        return strip_non_blank(value, info.field_name)

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
    coordination_headline: str
    coordination_owner_label: str
    coordination_detail: str | None = None
    action_required_by: str | None = None
    action_required_summary: str | None = None
    responsibility_stage: ResponsibilityStage | None = None
    owner_scope: OwnerScope | None = None
    created_by: uuid.UUID
    created_by_name: str
    responsibility_owner: ResponsibilityOwner | None = None
    assigned_org_id: uuid.UUID | None = None
    assigned_org_name: str | None = None
    assigned_contractor_user_id: uuid.UUID | None = None
    assigned_contractor_name: str | None = None
    assignee_scope: OwnerScope | None = None
    assignee_label: str | None = None
    latest_event_type: EventType | None = None
    latest_event_actor_label: str | None = None
    latest_event_at: datetime | None = None
    latest_resident_update_message: str | None = None
    latest_resident_update_actor_label: str | None = None
    latest_resident_update_at: datetime | None = None
    latest_operations_update_message: str | None = None
    latest_operations_update_actor_label: str | None = None
    latest_operations_update_at: datetime | None = None
    latest_contractor_update_message: str | None = None
    latest_contractor_update_actor_label: str | None = None
    latest_contractor_update_at: datetime | None = None
    pending_signal_headline: str | None = None
    pending_signal_summary: str | None = None
    pending_signal_actor_label: str | None = None
    pending_signal_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
