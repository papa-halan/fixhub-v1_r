from __future__ import annotations

import unittest
import uuid
from unittest.mock import Mock, patch

from app.models import MaintenanceRequest, WorkOrder, WorkOrderStatus
from app.services.maintenance_coordination import MaintenanceCoordinationService


class TransitionSession:
    def __init__(
        self,
        *,
        work_order: WorkOrder,
        request: MaintenanceRequest,
        residence_id: uuid.UUID,
    ) -> None:
        self._objects = {
            (WorkOrder, work_order.work_order_id): work_order,
            (MaintenanceRequest, request.request_id): request,
        }
        self._residence_id = residence_id
        self.flush_calls = 0
        self.refresh_calls: list[tuple[object, list[str] | None]] = []

    def get(self, model: type[object], identifier: uuid.UUID) -> object | None:
        return self._objects.get((model, identifier))

    def scalar(self, _statement: object) -> uuid.UUID:
        return self._residence_id

    def flush(self) -> None:
        self.flush_calls += 1

    def refresh(self, obj: object, attribute_names: list[str] | None = None) -> None:
        self.refresh_calls.append((obj, attribute_names))


class MaintenanceCoordinationServiceTests(unittest.TestCase):
    def test_completed_transition_refreshes_db_managed_completed_at(self) -> None:
        org_id = uuid.uuid4()
        contractor_user_id = uuid.uuid4()
        request = MaintenanceRequest(
            request_id=uuid.uuid4(),
            org_id=org_id,
            unit_id=uuid.uuid4(),
            resident_user_id=uuid.uuid4(),
            category="plumbing",
            description="Tap is leaking",
        )
        work_order = WorkOrder(
            work_order_id=uuid.uuid4(),
            org_id=org_id,
            request_id=request.request_id,
            contractor_user_id=contractor_user_id,
            status=WorkOrderStatus.in_progress,
        )
        session = TransitionSession(
            work_order=work_order,
            request=request,
            residence_id=uuid.uuid4(),
        )
        policy = Mock()
        service = MaintenanceCoordinationService(session=session, policy=policy)

        with patch("app.services.maintenance_coordination.append_event") as append_event:
            result = service._transition_for_contractor(
                work_order_id=work_order.work_order_id,
                contractor_user_id=contractor_user_id,
                to_status=WorkOrderStatus.completed,
            )

        self.assertIs(result, work_order)
        self.assertEqual(work_order.status, WorkOrderStatus.completed)
        self.assertEqual(session.flush_calls, 1)
        self.assertEqual(session.refresh_calls, [(work_order, ["completed_at"])])
        policy.require_assigned_contractor.assert_called_once_with(
            work_order=work_order,
            contractor_user_id=contractor_user_id,
        )
        append_event.assert_called_once()

    def test_non_completed_transition_does_not_refresh_completed_at(self) -> None:
        org_id = uuid.uuid4()
        contractor_user_id = uuid.uuid4()
        request = MaintenanceRequest(
            request_id=uuid.uuid4(),
            org_id=org_id,
            unit_id=uuid.uuid4(),
            resident_user_id=uuid.uuid4(),
            category="electrical",
            description="Light is flickering",
        )
        work_order = WorkOrder(
            work_order_id=uuid.uuid4(),
            org_id=org_id,
            request_id=request.request_id,
            contractor_user_id=contractor_user_id,
            status=WorkOrderStatus.assigned,
        )
        session = TransitionSession(
            work_order=work_order,
            request=request,
            residence_id=uuid.uuid4(),
        )
        service = MaintenanceCoordinationService(session=session, policy=Mock())

        with patch("app.services.maintenance_coordination.append_event"):
            service._transition_for_contractor(
                work_order_id=work_order.work_order_id,
                contractor_user_id=contractor_user_id,
                to_status=WorkOrderStatus.in_progress,
            )

        self.assertEqual(session.refresh_calls, [])
