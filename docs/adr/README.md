# ADR Index

| Metadata | Value |
| --- | --- |
| Docs version | 0.2.0 |
| Status | Active |
| Owner | Architecture maintainer |
| Reviewers | Project maintainer; docs maintainer |
| Last updated | 2026-03-13 |
| Review cadence | On change and quarterly |

This directory records architecture decision records for implemented model choices that materially shape the current codebase.

## ADR Status Meanings

- Accepted: implemented and treated as current direction.
- Superseded: replaced by a later ADR.
- Proposed: drafted but not yet implemented.

## Current ADRs

- [`ADR 0001`](0001-one-request-one-work-order.md): one maintenance request maps to one work order in the MVP.
- [`ADR 0002`](0002-minimal-role-and-status-enums.md): roles and lifecycle enums remain intentionally small in the MVP.
- [`ADR 0003`](0003-append-only-domain-events-with-audit.md): domain events are append-only and each event creates an audit entry in the same unit of work.

## Change Log

- 2026-03-13 15:52:00 +11:00 (Australia/Sydney): Added initial ADR history for current MVP model decisions.
