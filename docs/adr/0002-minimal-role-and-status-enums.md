# ADR 0002: Minimal Role and Status Enums for the MVP

| Metadata | Value |
| --- | --- |
| Docs version | 0.2.0 |
| Status | Accepted |
| Owner | Architecture maintainer |
| Reviewers | Project maintainer; docs maintainer |
| Last updated | 2026-03-13 |
| Review cadence | On change and quarterly |

## Context

The current implementation uses intentionally small enums to keep authorization and workflow transitions narrow:
- `UserRole`: `resident`, `staff`, `contractor`
- `WorkOrderStatus`: `assigned`, `in_progress`, `completed`
- `IntegrationJobStatus`: `requested`, `completed`, `failed`

This aligns with the present workflow service, policy checks, and tests.

## Decision

Keep role and lifecycle enums minimal for the MVP rather than modeling broader operational states and actor sub-types.

## Consequences

Positive:
- Policy rules stay easy to implement and test.
- Work-order transition rules remain explicit and low risk.
- Seed data and smoke-test setup stay compact.

Negative:
- Staff sub-responsibilities are not modeled explicitly.
- Contractor archetypes are flattened into one role.
- Operational lifecycle states such as `on_hold` or `cancelled` are deferred.

## Rationale for Acceptance

This choice reflects the current code rather than an aspirational future model. Broader role and status modeling can be introduced later when the API and operational workflow expand.
