# Documentation Index

Last updated: `2026-03-15 18:31:34 +11:00`

## Purpose

This folder stores project documentation for implemented behavior and ongoing documentation governance.

## Structure

- [CHANGELOG.md](CHANGELOG.md): timestamped documentation updates.
- [schema_student_living_assessment.md](schema_student_living_assessment.md): schema/workflow validation, SD sanity checks, and TODO proposals.
- [todo_implementation_checklist.md](todo_implementation_checklist.md): implementation checklist for proposed TODO backlog.

## Documentation Standards

- describe implemented behavior as facts and evidence.
- place all proposed future changes under explicit `TODO (Proposed)` sections.
- prefer repository-relative links to keep docs portable across environments.
- include update timestamp and authoring context for traceability.

## SD Practice Sanity Check

- Versioning and timestamped history: pass (`CHANGELOG.md` + dated run entries).
- Separation of current-state vs proposed-state: pass (`Implemented` vs `TODO` sections).
- Portability/readability for sharing with other users: pass (relative links + index).
- Verification evidence attached to claims: pass (schema/app pytest coverage is green in this environment).
- README diagram coverage for current implementation: pass (ER + flow + architecture + state machine documented with Mermaid, including location/asset catalog).

## Suggestions For Development Documentation

- keep one owner/reviewer field per major document once team roles stabilize.
- add a short "How to update docs after code changes" SOP to reduce drift.
- standardize a "Validation Evidence" section format across docs.

## TODO (Proposed Documentation Improvements)

- add role-oriented user journey docs under `docs/flows/` once flows are stable.
- add a compact ADR folder for key data-model decisions if schema expands.
- automate a docs freshness check tied to changed app/test/template files.

## Process Feedback Against Standard SD Practice

- current process now follows baseline SD practice for traceability and structure, but review cadence is still manual.
- evidence quality now includes green runtime checks for schema/app coverage, but review cadence is still manual.
- proposed-vs-implemented separation is now explicit, reducing requirement ambiguity for reviewers.
- diagram updates are now captured as first-class documentation changes, but should eventually move to dedicated architecture docs under `docs/` for long-term maintainability.
