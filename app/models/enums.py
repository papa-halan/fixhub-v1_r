from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    resident = "resident"
    contractor = "contractor"
    staff = "staff"


class WorkOrderStatus(str, Enum):
    assigned = "assigned"
    in_progress = "in_progress"
    completed = "completed"


class IntegrationJobStatus(str, Enum):
    requested = "requested"
    completed = "completed"
    failed = "failed"


EVENT_MAINTENANCE_REQUEST_SUBMITTED = "uon.maintenance_request.submitted"
EVENT_WORK_ORDER_CREATED = "uon.work_order.created"
EVENT_WORK_ORDER_STATUS_CHANGED = "uon.work_order.status_changed"
EVENT_INTEGRATION_REQUESTED = "uon.integration.requested"
EVENT_INTEGRATION_COMPLETED = "uon.integration.completed"
EVENT_INTEGRATION_FAILED = "uon.integration.failed"

EVENT_TYPES = (
    EVENT_MAINTENANCE_REQUEST_SUBMITTED,
    EVENT_WORK_ORDER_CREATED,
    EVENT_WORK_ORDER_STATUS_CHANGED,
    EVENT_INTEGRATION_REQUESTED,
    EVENT_INTEGRATION_COMPLETED,
    EVENT_INTEGRATION_FAILED,
)