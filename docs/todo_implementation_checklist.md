# TODO Implementation Checklist

Last updated: `2026-03-19 15:24:12 +11:00`

## Document Metadata

- Owner: `student-living-platform`
- Reviewer: `schema-test-automation`
- Status: `active`

Use this checklist to implement the current proposed TODO backlog in a controlled order.

## Pre-Work

- [x] Confirm current baseline passes relevant tests in target environment.
- [ ] Create a feature branch for TODO implementation work.
- [x] Review current TODO sources:
- [x] `README.md` -> `Documentation TODO (Proposed)`
- [x] `docs/schema_student_living_assessment.md` -> `TODO (Proposed Product Improvements)` + `TODO (Proposed Documentation Improvements)`
- [x] `docs/README.md` -> `TODO (Proposed Documentation Improvements)`

## Track A: Product TODOs

### A1. Lifecycle States (blocked/reopen/escalation)

- [x] Extend job status model with required new states.
- [x] Define explicit allowed transitions for each role.
- [x] Update API validation and response handling.
- [x] Update UI status presentation for new states.
- [x] Add tests for valid transitions and forbidden transitions.

Acceptance checks:
- [x] No implicit backward transition occurs.
- [x] Resident/admin/contractor role permissions are enforced.

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

- [x] Expand role model (e.g., reception_admin, triage_officer, coordinator).
- [x] Update auth/permission checks by route and action.
- [x] Update seed/demo users for each role.
- [x] Ensure event/audit labels reflect accountable actor.
- [x] Add tests for role-scoped access.

Acceptance checks:
- [x] Role boundaries are observable in API + UI behavior.
- [x] Unauthorized actions return expected errors.

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

- [x] Create `docs/architecture.md` with flow diagram (Mermaid acceptable).
- [x] Include role pages, core API routes, entities, and event flow.

### B2. Documentation SOP

- [x] Create `docs/documentation_sop.md`.
- [x] Define when docs updates are mandatory after code changes.
- [x] Define required changelog update pattern.

### B3. Known Environment Issues

- [x] Create `docs/known_issues.md`.
- [x] Document Python `encodings` startup failure and mitigations.

### B4. Docs Freshness Gate

- [x] Add a docs freshness check script/test.
- [x] Integrate check into CI or local quality gate.
- [x] Document how to override/acknowledge intentional exceptions.

### B5. Owner/Reviewer Metadata

- [x] Define metadata convention in `docs/README.md`.
- [x] Apply metadata block to major docs.

Acceptance checks:
- [x] New docs are linked from `docs/README.md`.
- [x] `docs/CHANGELOG.md` records all documentation additions/changes.

## Validation and Release

- [x] Run tests and linters in target environment.
- [ ] Manually verify critical resident/admin/contractor flows.
- [x] Confirm docs reflect implemented state only.
- [x] Move remaining unimplemented items back into TODO sections.
- [x] Update `docs/CHANGELOG.md` with timestamped release notes.
- [x] Sync README Mermaid diagrams to currently implemented schema/routes/lifecycle only (no speculative states).
- [x] Refresh `docs/README.md` SD-practice sanity checks and process feedback against current repository state.
- [x] Append timestamped schema/doc sync run log entry in `docs/schema_student_living_assessment.md`.

Run note (`2026-03-19 15:04:12 +11:00`):
- commit review since last automation run found no new commits to triage.
- runtime execution remains blocked in this environment (`python`/`py` unavailable, venv python access denied), so validation remains pending.
- a minimal code fix was applied to align assignment permission error text with actual role checks.

Run note (`2026-03-19 15:12:17 +11:00`):
- commit review since automation last run (`2026-03-19T04:00:56.070Z`) found two commits to inspect: `f7877bd00ca0e4837f82db0364d73bcde83310ab` and `9c0a0b5397318d6d2a97774ade77e73de0ed0482`.
- no additional minimal bug fix was applied in this run because no new concrete regression was identified from commit diffs alone.
- runtime validation remains pending due environment execution blockers (`python` and `py` missing, `.venv\\Scripts\\python.exe` execution denied).

Run note (`2026-03-19 15:24:12 +11:00`):
- extracted lifecycle rules into `app/services/workflow.py` and expanded guarded-path coverage for blocked, on-hold, reopened, and explicit completion-accountability transitions.
- runtime verification succeeded locally with `.\.venv\Scripts\python.exe -m pytest tests\test_schema.py tests\test_app.py` (`23 passed`) and `.\.venv\Scripts\python.exe -m ruff check app tests`.
- this dirty worktree still contains older documentation entries timestamped later than the current environment clock; the timestamp above reflects the actual verification time for this pass.

## Definition of Done

- [ ] Product TODOs implemented with migrations and passing tests.
- [x] Documentation TODOs added, linked, and changelogged.
- [x] README/docs maintain explicit implemented vs proposed separation.
