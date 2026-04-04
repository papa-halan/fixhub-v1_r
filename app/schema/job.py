from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import ValidationInfo, field_validator

from app.models import EventType, JobStatus, OwnerScope, ReportChannel, ResponsibilityOwner, ResponsibilityStage
from app.schema.base import SchemaModel, strip_non_blank


class JobCreate(SchemaModel):
    title: str
    description: str
    location_id: uuid.UUID
    location_detail_text: str | None = None
    asset_name: str | None = None
    reported_for_user_id: uuid.UUID | None = None
    intake_channel: ReportChannel | None = None

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
    reported_for_user_id: uuid.UUID
    reported_for_user_name: str
    intake_channel: ReportChannel | None = None
    intake_channel_label: str | None = None
    intake_summary: str | None = None
    reported_by_actor_label: str | None = None
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
    latest_lifecycle_event_type: EventType | None = None
    latest_lifecycle_event_actor_label: str | None = None
    latest_lifecycle_event_at: datetime | None = None
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
    activity_gap_headline: str | None = None
    activity_gap_summary: str | None = None
    activity_gap_at: datetime | None = None
    visit_plan_headline: str | None = None
    visit_plan_summary: str | None = None
    visit_dispatch_message: str | None = None
    visit_dispatch_actor_label: str | None = None
    visit_dispatch_at: datetime | None = None
    visit_booking_message: str | None = None
    visit_booking_actor_label: str | None = None
    visit_booking_at: datetime | None = None
    visit_access_message: str | None = None
    visit_access_actor_label: str | None = None
    visit_access_at: datetime | None = None
    visit_blocker_message: str | None = None
    visit_blocker_actor_label: str | None = None
    visit_blocker_at: datetime | None = None
    operational_history_headline: str | None = None
    operational_history_summary: str | None = None
    operational_history_location_job_count: int = 0
    operational_history_asset_job_count: int = 0
    operational_history_open_job_count: int = 0
    created_at: datetime
    updated_at: datetime
