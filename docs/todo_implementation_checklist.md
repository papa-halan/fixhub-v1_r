# TODO Implementation Checklist

Last updated: `2026-03-13 23:28:11 +11:00`

Use this checklist to implement the current proposed TODO backlog in a controlled order.

## Pre-Work

- [ ] Confirm current baseline passes relevant tests in target environment.
- [ ] Create a feature branch for TODO implementation work.
- [ ] Review current TODO sources:
- [ ] `README.md` -> `Documentation TODO (Proposed)`
- [ ] `docs/schema_student_living_assessment.md` -> `TODO (Proposed Product Improvements)` + `TODO (Proposed Documentation Improvements)`
- [ ] `docs/README.md` -> `TODO (Proposed Documentation Improvements)`

## Track A: Product TODOs

### A1. Lifecycle States (blocked/reopen/escalation)

- [ ] Extend job status model with required new states.
- [ ] Define explicit allowed transitions for each role.
- [ ] Update API validation and response handling.
- [ ] Update UI status presentation for new states.
- [ ] Add tests for valid transitions and forbidden transitions.

Acceptance checks:
- [ ] No implicit backward transition occurs.
- [ ] Resident/admin/contractor role permissions are enforced.

### A2. Request -> Work Order Split (1:N)

- [ ] Introduce resident-facing request entity.
- [ ] Introduce execution-facing work-order entity linked to request.
- [ ] Add DB migration(s) and update seed/demo behavior.
- [ ] Adapt APIs to create/read request + related work orders.
- [ ] Update timeline logic for aggregated request progress.
- [ ] Add tests for multi-work-order lifecycle.

Acceptance checks:
- [ ] One request supports multiple work orders.
- [ ] Existing resident flow remains functional.

### A3. Student Living Operational Roles

- [ ] Expand role model (e.g., reception_admin, triage_officer, coordinator).
- [ ] Update auth/permission checks by route and action.
- [ ] Update seed/demo users for each role.
- [ ] Ensure event/audit labels reflect accountable actor.
- [ ] Add tests for role-scoped access.

Acceptance checks:
- [ ] Role boundaries are observable in API + UI behavior.
- [ ] Unauthorized actions return expected errors.

### A4. Structured Visits and Routing Reasons

- [ ] Add appointment/visit structure (window, outcome, access-failure reason).
- [ ] Add routing decision records with reason codes.
- [ ] Integrate structured records into timeline rendering.
- [ ] Add tests for visit persistence and reason-coded routing.

Acceptance checks:
- [ ] Scheduling and reroute context is queryable, not free-text only.
- [ ] Timeline remains readable for residents.

## Track B: Documentation TODOs

### B1. Architecture Diagram

- [ ] Create `docs/architecture.md` with flow diagram (Mermaid acceptable).
- [ ] Include role pages, core API routes, entities, and event flow.

### B2. Documentation SOP

- [ ] Create `docs/documentation_sop.md`.
- [ ] Define when docs updates are mandatory after code changes.
- [ ] Define required changelog update pattern.

### B3. Known Environment Issues

- [ ] Create `docs/known_issues.md`.
- [ ] Document Python `encodings` startup failure and mitigations.

### B4. Docs Freshness Gate

- [ ] Add a docs freshness check script/test.
- [ ] Integrate check into CI or local quality gate.
- [ ] Document how to override/acknowledge intentional exceptions.

### B5. Owner/Reviewer Metadata

- [ ] Define metadata convention in `docs/README.md`.
- [ ] Apply metadata block to major docs.

Acceptance checks:
- [ ] New docs are linked from `docs/README.md`.
- [ ] `docs/CHANGELOG.md` records all documentation additions/changes.

## Validation and Release

- [ ] Run tests and linters in target environment.
- [ ] Manually verify critical resident/admin/contractor flows.
- [ ] Confirm docs reflect implemented state only.
- [ ] Move remaining unimplemented items back into TODO sections.
- [ ] Update `docs/CHANGELOG.md` with timestamped release notes.

## Definition of Done

- [ ] Product TODOs implemented with migrations and passing tests.
- [ ] Documentation TODOs added, linked, and changelogged.
- [ ] README/docs maintain explicit implemented vs proposed separation.
