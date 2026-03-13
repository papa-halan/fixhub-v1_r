# FixHub v1 - Maintenance Coordination MVP

| Metadata | Value |
| --- | --- |
| Docs version | 0.2.0 |
| Status | Active |
| Owner | Project maintainer |
| Reviewers | Docs maintainer; project maintainer |
| Last updated | 2026-03-13 |
| Review cadence | On change and quarterly |

This repository currently implements the data/model and service workflow for a maintenance coordination MVP (resident -> staff dispatch -> contractor execution), with event and audit tracking.

## Current Project State (Implemented)

- PostgreSQL schema and Alembic migrations for the MVP domain.
- SQLAlchemy models for organisations, residences, units, users, maintenance requests, work orders, routing rules, domain events, integration jobs, and audit entries.
- Transaction-scoped workflow service in `app/services/maintenance_coordination.py`.
- Supporting services for policy checks, event append/integration jobs, routing, auth, and password hashing.
- Seed and smoke-test scripts (`scripts/seed_mvp.py`, `scripts/smoke_test_mvp.py`).
- Unit tests for auth, events, maintenance coordination, policies, and password handling.

Not implemented as source code in this repository:
- Runnable HTTP API entrypoint and route modules. `app/main.py` is intentionally empty; only cached route bytecode exists under `app/api/**/__pycache__`.

## Documentation Structure

- [`docs/README.md`](docs/README.md): documentation map, conventions, and review rules.
- [`docs/CHANGELOG.md`](docs/CHANGELOG.md): versioned documentation changelog.
- [`docs/adr/README.md`](docs/adr/README.md): ADR index for core model choices already implemented.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): implemented architecture and boundaries.
- [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md): local setup, validation commands, and documentation process guidance.
- [`docs/SECURITY.md`](docs/SECURITY.md): current security posture and known production gaps.
- [`docs/schema_student_living_assessment.md`](docs/schema_student_living_assessment.md): resident workflow schema/service assessment.

## Documentation Practice Check (SD Standards)

Current documentation now follows these baseline software-development documentation practices:
- Explicit separation of implemented behavior vs proposed improvements.
- Versioned docs change tracking in `docs/CHANGELOG.md`.
- ADR history for implemented model choices.
- Owner/reviewer metadata and review cadence on each maintained document.
- Clear ownership boundaries and known limitations.
- Actionable TODO lists for forward work.

## TODO (Proposed Improvements)

- TODO: Add an API contract document once HTTP routes are restored as source files.
- TODO: Add a docs template for new design notes, runbooks, and assessments.
- TODO: Automate reminders for quarterly document review dates.

## Documentation Change Log

- 2026-03-13 15:52:00 +11:00 (Australia/Sydney): Added ADR history, versioned docs changelog, and owner/reviewer metadata across the docs set.
- 2026-03-13 15:21:56 +11:00 (Australia/Sydney): Refactored README and docs structure to improve clarity, separated current implementation from proposals, added TODO tracking and SD-practice review notes.
