# ADR 0003: Append-Only Domain Events with Same-Transaction Audit Entries

| Metadata | Value |
| --- | --- |
| Docs version | 0.2.0 |
| Status | Accepted |
| Owner | Architecture maintainer |
| Reviewers | Project maintainer; docs maintainer |
| Last updated | 2026-03-13 |
| Review cadence | On change and quarterly |

## Context

The current system persists domain events in `DomainEvent` as an internal append-only event log/outbox table. Each appended event also creates one `AuditEntry` in the same unit of work.

Implementation evidence:
- `app/services/events.py::append_event()` creates both `DomainEvent` and `AuditEntry`.
- The stored event shape is CloudEvents-inspired but not a full CloudEvents document.

## Decision

Keep event persistence append-only and couple audit creation to event creation inside the same transaction scope.

## Consequences

Positive:
- Workflow actions preserve an auditable trail by default.
- Integration jobs can reference event history without separate audit plumbing.
- The event model remains simple enough for current scripts and tests.

Negative:
- The event schema is not yet a canonical CloudEvents implementation.
- Future export/integration layers will need explicit mapping if formal CloudEvents are required.

## Rationale for Acceptance

This decision reflects the current implementation and supports the MVP goal of traceable workflow state changes without introducing a separate message bus or audit subsystem.
