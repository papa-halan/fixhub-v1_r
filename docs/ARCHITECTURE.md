# Architecture

| Metadata | Value |
| --- | --- |
| Docs version | 0.2.0 |
| Status | Active |
| Owner | Architecture maintainer |
| Reviewers | Project maintainer; docs maintainer |
| Last updated | 2026-03-13 |
| Review cadence | On change and quarterly |

## Current State (Implemented)

The repository currently provides:
- SQLAlchemy models and Alembic migrations for the maintenance coordination MVP.
- Transaction-scoped coordination workflow in `app/services/maintenance_coordination.py`.
- Cross-cutting service modules:
  - `app/services/policy.py` for role/org authorization.
  - `app/services/events.py` for event append + integration-job creation.
  - `app/services/routing.py` for contractor resolution by `(residence_id, category)`.

The repository currently does not provide:
- Runnable HTTP API source modules. `app/main.py` is empty.

## Session and Unit-of-Work Model

Database access uses `session_scope()` in `app/core/database.py`.
- One `Session` per unit of work.
- Commit/rollback at unit-of-work boundary.
- Do not share sessions across concurrent execution contexts.

## Domain and Event Model

Implemented workflow:
1. Resident submits maintenance request.
2. Staff dispatches request to work order.
3. Contractor progresses work order (`assigned -> in_progress -> completed`).
4. Integration jobs are requested and recorded as completed/failed.

`DomainEvent` is an internal append-only event log/outbox table (CloudEvents-inspired subset):
- Stored: `event_id`, `type`, `source`, `subject_id`, `time`, `partition_key`, `routing_key`, `actor_user_id`, `data`.
- Not stored as formal CloudEvents fields: `specversion`, `datacontenttype`, `dataschema`, string `subject`.

For each domain event:
- One `AuditEntry` is appended in the same transaction.

## Architecture Boundaries

- Domain logic boundary: `MaintenanceCoordinationService`.
- Policy boundary: `AuthorisationPolicy`.
- Event/integration side-effect boundary: event append + integration-job request helpers.

## Relevant ADRs

- [`ADR 0001`](adr/0001-one-request-one-work-order.md): one maintenance request maps to one work order in the MVP.
- [`ADR 0002`](adr/0002-minimal-role-and-status-enums.md): roles and lifecycle enums stay intentionally small in the MVP.
- [`ADR 0003`](adr/0003-append-only-domain-events-with-audit.md): domain events are append-only and coupled with audit entries.

## TODO (Proposed)

- TODO: Introduce formal API boundary docs after route source files are restored.
- TODO: Add sequence diagrams for each workflow command.
- TODO: Add explicit failure-mode matrix (routing missing, integration retry, DB rollback scenarios).

## SD Practice Check and Feedback

Good:
- Boundary ownership is clearer than before.
- Cross-cutting concerns are factored into dedicated modules.
- Core MVP model choices now have ADR coverage.

Needs improvement:
- Missing API implementation limits architectural traceability from user action to service call.
- Sequence-level runtime behavior is still implicit rather than diagrammed per command path.

## Change Log

- 2026-03-13 15:52:00 +11:00 (Australia/Sydney): Added document metadata and linked ADR history for implemented model decisions.
- 2026-03-13 15:21:56 +11:00 (Australia/Sydney): Refactored architecture doc to separate implemented scope from proposals and added SD-practice checks.
