# Documentation Index

| Metadata | Value |
| --- | --- |
| Docs version | 0.2.0 |
| Status | Active |
| Owner | Docs maintainer |
| Reviewers | Project maintainer; docs maintainer |
| Last updated | 2026-03-13 |
| Review cadence | On change and quarterly |

This folder documents the implemented state of FixHub v1 and tracks proposed improvements separately.

## Reading Order

1. [`../README.md`](../README.md) - project overview and the top-level documentation entrypoint.
2. [`CHANGELOG.md`](CHANGELOG.md) - version history for the documentation set.
3. [`adr/README.md`](adr/README.md) - ADR index for implemented model decisions.
4. [`ARCHITECTURE.md`](ARCHITECTURE.md) - domain boundaries, data/event model, and service responsibilities.
5. [`DEVELOPMENT.md`](DEVELOPMENT.md) - local setup, verification commands, and contribution/documentation workflow.
6. [`SECURITY.md`](SECURITY.md) - current controls and production gaps.
7. [`schema_student_living_assessment.md`](schema_student_living_assessment.md) - workflow fit assessment for Student Living use cases.

## Documentation Rules (Current)

- Document only implemented behavior in "Current State" sections.
- Put non-implemented ideas in `TODO (Proposed)` sections.
- Record docs-set version changes in [`CHANGELOG.md`](CHANGELOG.md).
- Include owner/reviewer metadata in every maintained markdown document.
- Prefer repository-relative links for portability and sharing.

## SD Documentation Sanity Check

Aligned:
- Scope and status are explicit.
- Operational commands are reproducible.
- Known gaps and risks are documented.
- Improvement backlog is visible.
- Decision history exists for core MVP model choices.
- Ownership and review cadence are declared per document.

Needs improvement:
- Add a reusable documentation template for new docs.
- Automate review reminders against the declared review cadence.
- Map role-based owners to named maintainers if the contributor group grows.

## Change Log

- 2026-03-13 15:52:00 +11:00 (Australia/Sydney): Added ADR and changelog references, plus metadata requirements for all maintained docs.
- 2026-03-13 15:21:56 +11:00 (Australia/Sydney): Added docs index and normalized docs conventions.
