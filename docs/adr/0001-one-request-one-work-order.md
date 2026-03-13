# ADR 0001: One Maintenance Request Maps to One Work Order in the MVP

| Metadata | Value |
| --- | --- |
| Docs version | 0.2.0 |
| Status | Accepted |
| Owner | Architecture maintainer |
| Reviewers | Project maintainer; docs maintainer |
| Last updated | 2026-03-13 |
| Review cadence | On change and quarterly |

## Context

The current MVP focuses on the simplest dispatch flow from a resident-submitted maintenance request to contractor execution. The existing schema and service layer treat dispatch as a single conversion step from request to work order.

Implementation evidence:
- `work_orders.request_id` is treated as unique in the current schema.
- `MaintenanceCoordinationService._ensure_request_has_no_work_order()` blocks creation of a second work order for the same request.

## Decision

Keep the current MVP cardinality as one `MaintenanceRequest` to one `WorkOrder`.

## Consequences

Positive:
- Dispatch logic stays small and easy to reason about.
- Resident request status lookup can assume at most one linked work order.
- Event partitioning and work-order ownership remain straightforward.

Negative:
- Multi-trade or split execution is not supported.
- Re-dispatch or decomposition workflows require future schema changes.

## Rationale for Acceptance

This choice matches the current codebase and keeps the MVP aligned to a narrow, testable coordination flow.
