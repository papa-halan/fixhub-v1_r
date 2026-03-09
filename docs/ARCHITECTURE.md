# Architecture

## Current boundary

The repository currently provides:

- SQLAlchemy models and Alembic migrations for the maintenance coordination MVP.
- A transaction-scoped service layer in [`app/services/maintenance_coordination.py`](/C:/Users/halan/PycharmProjects/fixhub-v1/app/services/maintenance_coordination.py).
- Seed and smoke-test scripts in `scripts/`.

The repository does not currently provide a runnable HTTP API. Files under `app/api/` and `app/main.py` are placeholders.

## Session model

Database access is built around [`session_scope()`](/C:/Users/halan/PycharmProjects/fixhub-v1/app/core/database.py:14):

- Create one `Session` per request, script run, or unit of work.
- Commit or roll back at the unit-of-work boundary.
- Do not share a `Session` across concurrent threads or async tasks.

`MaintenanceCoordinationService` assumes the caller provides a transaction-scoped session and that all work for a command runs inside that transaction.

## Event model

The MVP stores domain events in [`DomainEvent`](/C:/Users/halan/PycharmProjects/fixhub-v1/app/models/mvp.py:188). This is an internal event log/outbox table, not a full CloudEvents implementation.

Persisted fields:

- `event_id`
- `type`
- `source`
- `subject_id`
- `time`
- `partition_key`
- `routing_key`
- `actor_user_id`
- `data`

Operational behavior:

- Every domain event is append-only.
- Every domain event gets exactly one [`AuditEntry`](/C:/Users/halan/PycharmProjects/fixhub-v1/app/models/mvp.py:247).
- `partition_key` keeps related workflow events grouped for downstream processing.
- `routing_key` is derived from `org_id`, `residence_id`, and request category.

## Coordination service structure

[`MaintenanceCoordinationService`](/C:/Users/halan/PycharmProjects/fixhub-v1/app/services/maintenance_coordination.py) now delegates two cross-cutting concerns into smaller modules:

- [`app/services/policy.py`](/C:/Users/halan/PycharmProjects/fixhub-v1/app/services/policy.py): authorization and org-scope checks.
- [`app/services/events.py`](/C:/Users/halan/PycharmProjects/fixhub-v1/app/services/events.py): event append and integration-job creation.

This reduces the amount of mixed policy/persistence/event code in the main workflow service, but the coordination service is still the main domain hotspot in the codebase.
