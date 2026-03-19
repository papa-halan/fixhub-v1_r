# Schema Test: UoN Student Living Resident Reporting

Date: `2026-03-15 18:31:34 +11:00`
Scope: code-level schema and workflow validation in [app/models/mvp.py](../app/models/mvp.py), [app/models/enums.py](../app/models/enums.py), [app/schema/__init__.py](../app/schema/__init__.py), [app/main.py](../app/main.py), [app/api/jobs.py](../app/api/jobs.py), [app/api/resident.py](../app/api/resident.py), [app/services/demo.py](../app/services/demo.py), [app/services/catalog.py](../app/services/catalog.py), [tests/test_app.py](../tests/test_app.py), and [tests/test_schema.py](../tests/test_schema.py).

## Implemented Baseline (Current State)

- Core entities now include: `organisations`, `users`, `locations`, `assets`, `jobs`, `events`.
- User roles remain: `resident`, `admin`, `contractor`.
- Organisation types remain: `university`, `contractor`.
- Job statuses remain: `new`, `assigned`, `in_progress`, `completed`.
- Effective lifecycle remains linear dispatch with event timeline evidence.
- API request/response contracts now live in `app/schema`, separate from SQLAlchemy persistence models in `app/models`.
- Resident reports now persist a user-scoped `location` plus a location-scoped `asset`, and later admin/contractor events inherit that same context.
- Browser access now requires an explicit demo-user sign-in instead of a default resident fallback.

## Implemented Changes Observed In This Run

- `DATABASE_URL` default in [app/core/config.py](../app/core/config.py) now targets PostgreSQL instead of SQLite.
- dedicated Pydantic API schema modules now exist in [app/schema/job.py](../app/schema/job.py), [app/schema/event.py](../app/schema/event.py), [app/schema/user.py](../app/schema/user.py), and [app/schema/organisation.py](../app/schema/organisation.py).
- API routes in [app/api/jobs.py](../app/api/jobs.py) now declare request payloads and `response_model` contracts from `app/schema`.
- persistent catalog behavior now lives in [app/models/location.py](../app/models/location.py), [app/models/asset.py](../app/models/asset.py), and [app/services/catalog.py](../app/services/catalog.py).
- resident reporting UI now captures `asset_name` and surfaces remembered location/asset suggestions from prior reports.
- UI forms now declare `method="post"` in:
- [app/templates/resident_report.html](../app/templates/resident_report.html)
- [app/templates/admin_job.html](../app/templates/admin_job.html)
- [app/templates/contractor_job.html](../app/templates/contractor_job.html)
- base template script loading changed in [app/templates/base.html](../app/templates/base.html) to non-deferred script include.
- coverage added in [tests/test_app.py](../tests/test_app.py): `test_report_page_wires_post_form`.
- schema coverage added in [tests/test_schema.py](../tests/test_schema.py) for source-file presence, route-schema wiring, and request validation behavior.

## Validation Evidence

- Structural evidence: schema footprint now asserts six tables (`assets`, `events`, `jobs`, `locations`, `organisations`, `users`).
- Contract evidence: dedicated API schema modules exist under `app/schema`, and route signatures/response models are validated in [tests/test_schema.py](../tests/test_schema.py).
- Workflow evidence: resident-admin-contractor flow still validates assignment, event creation, and status progression.
- Persistence evidence: jobs and events now store the same location/asset context, and resident report pages surface remembered suggestions from prior reports.
- Runtime execution in this environment: pass (`tests/test_schema.py` + `tests/test_app.py`, 28 tests passed).

## Resident-Centric Suitability Summary

- Intake creation and timeline visibility: pass.
- Assignment visibility and contractor updates: pass.
- Multi-trade dispatch, blocked states, reopen/escalation semantics: not implemented in current schema.
- Fine-grained Student Living role boundaries: not implemented in current role model.

## SD Documentation Practice Sanity Check

- Facts vs proposals separation: pass (this document now separates implemented and TODO).
- Source traceability to code/tests: pass (all current-state claims mapped to repository files).
- Portability for sharing: pass (repository-relative links; no machine-specific paths).
- Verification depth: pass (runtime schema/app checks executed successfully in this environment).

## Feedback On Documentation Process (Against Standard SD Practice)

- Positive: implemented-state logging is now explicit and timestamped, reducing ambiguity.
- Positive: docs now include a dedicated changelog and index, improving discoverability.
- Gap: runtime verification is now available, but command snippets should still be documented per run for repeatability.
- Gap: historical docs continuity relied on memory; persisted files were missing and had to be reconstructed.

## TODO (Proposed Product Improvements)

- add explicit blocked/on-hold/reopen/escalation lifecycle states.
- split resident request from execution work order for 1:N dispatch.
- model Student Living operational roles (reception/triage/coordinator) explicitly.
- add structured appointment/visit entities and reason-coded routing decisions.

## TODO (Proposed Documentation Improvements)

- add a repeatable schema test checklist section with expected commands and output snippets.
- add a dedicated "Known environment issues" doc for Python/runtime setup constraints.
- include an owner/reviewer metadata block per major document once team ownership is defined.

---

## Run Log: `2026-03-15 18:16:11 +11:00` (Manual schema-doc sync)

### Sync Scope

- Verified that the current API contract surface is implemented in `app/schema` and consumed by the FastAPI routers under `app/api`.
- Updated `README.md` to document the `app/models` vs `app/schema` separation and reflect the schema layer in the architecture diagram.
- Refreshed this assessment document and `docs/README.md` to match the current schema package and verification status.

### Validation Evidence

- Runtime verification: `tests/test_schema.py` and `tests/test_app.py` passed in this environment (`24 passed`).
- Contract checks cover dedicated schema source files, route payload/response wiring, and shared validation behavior for trimmed non-blank strings.
- Existing workflow tests still confirm resident/admin/contractor behavior against the documented MVP scope.

### Current-State Conclusion

- Documentation now matches the current codebase: ORM models live in `app/models`, API contracts live in `app/schema`, and both are covered by tests.

---

## Run Log: `2026-03-15 18:31:34 +11:00` (Manual location-asset persistence)

### Sync Scope

- Added first-class `locations` and `assets` persistence tied to resident reporting memory and reused across job/event context.
- Updated README and schema docs to reflect the expanded data model and resident report behavior.

### Validation Evidence

- Runtime verification: `tests/test_schema.py` and `tests/test_app.py` passed in this environment (`28 passed`).
- New coverage verifies the extra tables, remembered resident suggestions, and event-level persistence of `location_id` and `asset_id`.

### Current-State Conclusion

- Location and asset context now persists beyond job creation and stays attached to admin handling and contractor updates through the event log.

---

## Run Log: `2026-03-14 00:02:29 +11:00` (Automation `schema-test`)

### Test Context Used

- Resident persona: student at University of Newcastle Student Living.
- Contractor assumptions tested: maintenance team contractor org, independent contractor without org linkage.
- Admin assumptions tested: Student Living staff acting as reception admin + triage/coordinator through current `admin` role.

### Edge-Case + JLC Coverage Added

The following test cases were added in [tests/test_app.py](../tests/test_app.py):

1. `test_admin_cannot_assign_university_org_as_contractor`
- Validates schema-level assignment integrity (`OrganisationType.university` cannot be dispatched as contractor).
- Why it matters: protects Student Living team from accidental self-assignment loops.

2. `test_admin_clearing_assignment_moves_assigned_job_back_to_new`
- Validates assignment rollback behavior and event logging continuity.
- Why it matters: confirms partial triage reversals are represented in timeline evidence.

3. `test_cannot_skip_status_from_new_to_completed`
- Validates lifecycle transition guardrails.
- Why it matters: prevents incoherent close-outs that bypass triage/dispatch work.

4. `test_independent_contractor_without_org_cannot_access_assigned_jobs`
- Validates current inability for non-org contractors to receive/act on jobs.
- Why it matters: directly exposes a gap versus real contractor modes (independent vs org-based).

### Findings Against Assumed Issues

- Confirmed: current lifecycle is coherent for a strict linear path, but incomplete for real JLC branches (blocked/on-hold/reopen/escalate).
- Confirmed: schema remains abstracted away from Student Living operational responsibilities because all admin pathways collapse into one `admin` role.
- Confirmed: contractor modeling is too narrow for mixed delivery modes; assignment is org-only.
- Confirmed: event timeline supports auditability, but lacks structured reason codes and responsibility checkpoints.

### Refactor Suggestions (Prioritized)

1. Introduce explicit Student Living sub-roles.
- Add `reception_admin`, `triage_officer`, `coordinator` (or equivalent capability flags) with scoped permissions.
- Result: clearer responsibility boundaries and less handoff ambiguity.

2. Split `Resident Request` from `Work Order`.
- Model a 1:N relationship where one resident request can spawn multiple contractor jobs.
- Result: supports real triage and multi-trade dispatch patterns.

3. Expand lifecycle state machine.
- Add `triaged`, `scheduled`, `on_hold`, `blocked`, `cancelled`, `reopened`, `escalated`.
- Result: complete JLC traceability and reduced workflow incoherence.

4. Support independent-contractor dispatch.
- Allow direct contractor-user assignment when no contractor org is present, with policy checks.
- Result: accommodates mixed contractor supply in Student Living operations.

5. Add responsibility-coded timeline events.
- Store structured event metadata (`reason_code`, `responsibility_owner`, `handoff_type`) beyond free-text messages.
- Result: reliable analytics and clearer triage accountability.

### Verification Status

- Code-level coverage: expanded via tests above.
- Runtime execution: blocked in this environment by Python startup failure (`ModuleNotFoundError: No module named 'encodings'`).

---

## Run Log: `2026-03-14 01:02:00 +11:00` (Automation `schema-test`)

### Test Context Used

- Primary test actor: resident user (University of Newcastle student in Student Living).
- Assumed supporting actors only: Student Living admin/triage user and contractor personas (maintenance team, independent contractor without org).
- Scope target: full current Job Life Cycle (JLC) plus resident-facing edge cases.

### New Test Cases Added This Run

Added in [tests/test_app.py](../tests/test_app.py):

1. `test_resident_cannot_view_another_resident_job`
- What was tested: resident privacy boundary for same-organisation students.
- Why it matters: Student Living users must not leak one resident's report details to another resident.

2. `test_completed_job_cannot_be_reopened_in_current_lifecycle`
- What was tested: end-of-life behavior after `completed`.
- Why it matters: confirms current lifecycle has no reopen path, which conflicts with common real-world defect recurrence.

3. `test_admin_can_clear_assignment_while_in_progress_leaving_unassigned_work`
- What was tested: assignment removal while job remains `in_progress`.
- Why it matters: exposes a JLC coherence gap where ownership can be removed without status rollback or reassignment checkpoint.

### JLC + Edge-Case Outcomes (Resident-Centric)

- `new -> assigned -> in_progress -> completed`: implemented and coherent for straight-through flow.
- `completed -> in_progress` reopen attempt: rejected (`400`), confirming missing reopen lifecycle.
- Mid-execution de-assignment: allowed, creating an unassigned `in_progress` job; this is operationally ambiguous for resident updates and accountability.
- Resident cross-report access: blocked (`403`), matching expected resident privacy.

### Refactor Suggestions (Mapped To Test Outcomes)

1. Add reopen/escalation lifecycle states.
- Suggested states: `reopened`, `escalated`, and optional `verification_pending`.
- Reason: `test_completed_job_cannot_be_reopened_in_current_lifecycle` shows no safe path for repeat faults after completion.

2. Enforce assignee-state consistency rules.
- Add invariant: `in_progress` and `completed` require active assignment (or explicit direct-contractor owner entity).
- Reason: `test_admin_can_clear_assignment_while_in_progress_leaving_unassigned_work` reveals ownership gaps.

3. Separate resident request from execution ownership.
- Model `resident_request` plus one-or-more `work_orders` with independent assignees/status.
- Reason: supports triage branching while preserving a resident-visible parent timeline.

4. Model Student Living responsibility stages explicitly.
- Add responsibility markers (`reception`, `triage`, `coordination`) as fields or typed events.
- Reason: reduces ambiguity on who owns the next action at each handoff.

### Verification Status

- Code-level evidence: expanded with resident/JLC edge-case tests listed above.
- Runtime execution in this environment: still blocked by Python startup error (`ModuleNotFoundError: No module named 'encodings'`), so verification remains static/code-level for this run.

---

## Run Log: `2026-03-14 02:01:00 +11:00` (Automation `schema-test`)

### Test Context Used

- Primary actor under test: resident student within University of Newcastle Student Living.
- Supporting assumptions only: Student Living admin acts as reception + triage + coordinator under current single `admin` role.
- Contractor assumptions only: maintenance contractor organisation and independent contractor mode constraints from prior runs.

### New Edge-Case + Full JLC Tests Added

Added in [tests/test_app.py](../tests/test_app.py):

1. `test_contractor_can_complete_directly_from_assigned`
- What was tested: lifecycle jump `assigned -> completed` without an `in_progress` checkpoint.
- Result: allowed by current state machine.
- Why this matters: resident loses execution transparency (no explicit active-work stage).

2. `test_admin_can_complete_job_without_contractor_status_update`
- What was tested: Student Living admin can mark a job complete even though contractor is assigned.
- Result: allowed by current permissions/transition logic.
- Why this matters: role boundary between triage/coordinator and execution owner is blurred for resident-facing accountability.

3. `test_resident_can_add_follow_up_event_after_completion_without_reopen_path`
- What was tested: resident can post follow-up evidence after completion but cannot reopen the job.
- Result: follow-up event accepted (`201`), reopen status change blocked (`403`), job remains `completed`.
- Why this matters: recurrence is captured only as free-text timeline noise, not as a structured reopened lifecycle.

### JLC Assessment (Resident Reporting Reality)

- Supported path: `new -> assigned -> in_progress -> completed`.
- Also supported path (edge): `new -> assigned -> completed` (no explicit work-in-progress phase).
- Unsupported resident recurrence path: `completed -> reopened`.
- Responsibility ambiguity remains: admin can assign and also close, while contractor closure is optional.

### Refactor Suggestions (Mapped To This Run)

1. Tighten lifecycle transition invariants.
- Remove direct `assigned -> completed`; require `in_progress` before completion.
- Benefit: preserves a resident-visible execution stage and clearer service timeline.

2. Separate coordination authority from completion authority.
- Keep assignment/triage with Student Living admins; restrict completion to execution owner (contractor) or explicit override with reason code.
- Benefit: reduces responsibility confusion for reception/triage/coordinator operations.

3. Add first-class recurrence/reopen workflow.
- Introduce `reopened` (and optionally `verification_pending`) with linkage to prior completion event.
- Benefit: resident follow-up becomes a structured lifecycle branch instead of unstructured comments.

4. Introduce structured event metadata.
- Add `event_type`, `reason_code`, and `responsibility_owner` fields.
- Benefit: clear handoff evidence across Student Living and contractor actors.

### Verification Status

- Code-level coverage: expanded with 3 additional tests listed above.
- Runtime pytest execution in this environment: still blocked by Python startup issue (`ModuleNotFoundError: No module named 'encodings'`).

---

## Run Log: `2026-03-15 17:31:20 +11:00` (Automation `schema-test`)

### Test Context Used

- Primary actor under test: resident student in University of Newcastle Student Living.
- Supporting assumptions only: Student Living admin performs reception admin + triage/coordinator actions via current `admin` role.
- Contractor modes tested against assumptions: contractor org team, maintenance team contractor org, and independent contractor without org membership.

### New Edge-Case + Full JLC Tests Added

Added in [tests/test_app.py](../tests/test_app.py):

1. `test_maintenance_team_contractor_org_can_be_assigned_and_progress_job`
- What was tested: a maintenance-team style contractor org can be assigned and complete the full execution path (`assigned -> in_progress -> completed`).
- Result: supported.
- Why this matters: validates one real delivery mode (contractors working as part of an organisation) for resident reports.

2. `test_independent_contractor_cannot_progress_job_without_org_dispatch_path`
- What was tested: independent contractor user with `organisation_id=None` attempts to progress a dispatched job.
- Result: blocked (`403`) due to no visibility/dispatch path.
- Why this matters: confirms schema gap for independent-contractor execution mode assumed in operations.

3. `test_admin_can_reassign_completed_job_without_reopen_or_status_change`
- What was tested: admin reassigns contractor org after contractor marks job `completed`.
- Result: allowed; job remains `completed` while assignee changes and timeline logs a reassignment event.
- Why this matters: lifecycle allows post-completion ownership churn without reopen, which is incoherent in real JLC accountability.

### JLC Assessment (Resident Reporting Reality)

- Straight path remains valid: `new -> assigned -> in_progress -> completed`.
- Contractor-org mode remains operational (including maintenance team as contractor organisation type).
- Independent-contractor mode remains non-dispatchable in current schema.
- Post-completion reassignment is currently allowed without reopening or verification state, creating responsibility ambiguity for Student Living staff and residents.

### Refactor Suggestions (Mapped To This Run)

1. Add first-class assignee model supporting both organisation and individual contractor assignment.
- Introduce `assigned_contractor_user_id` (nullable) alongside `assigned_org_id` with mutual-exclusion rules.
- Benefit: enables independent-contractor dispatch while preserving current org-based assignment.

2. Enforce completion immutability without explicit reopen workflow.
- Block assignment changes when status is `completed` unless status first transitions to `reopened` (or equivalent).
- Benefit: prevents silent ownership changes after closure and improves resident trust in finalised jobs.

3. Split Student Living admin capabilities into explicit responsibility stages.
- Add capability flags or sub-roles for reception intake, triage routing, and coordinator override.
- Benefit: removes current ambiguity where a single admin identity can both dispatch and close jobs.

4. Add structured completion/reassignment reason metadata.
- Add event fields such as `event_type`, `reason_code`, and `owner_scope` for assignment and closure transitions.
- Benefit: gives auditable accountability when handoffs or overrides occur in the lifecycle.

### Verification Status

- Code-level coverage: expanded with 3 additional tests listed above.
- Runtime pytest execution in this environment: blocked by Python startup failure (`ModuleNotFoundError: No module named 'encodings'`), so this run remains static/code-level verified.

---

## Run Log: `2026-03-15 17:30:56 +11:00` (Automation `refactor-docs-and-readme-md`)

### Documentation Sync Scope

- Verified that schema/app behavior claims in this document still match current code and test coverage in [tests/test_app.py](../tests/test_app.py).
- Updated `README.md` diagrams to include ER, flow chart, architecture, and state-machine views of currently implemented behavior.
- No additional schema/model/API behavior was introduced in this run.

### SD Practice Check (This Run)

- Implemented-vs-proposed separation: pass.
- Traceability to repository files/tests: pass.
- Cross-user portability: pass (repository-relative links maintained).
- Runtime verification depth: partial (pytest blocked by Python startup environment issue).

### TODO (Proposed, Documentation Process)

- move architecture narrative into dedicated `docs/architecture.md` once the architecture doc track is started.
- add an explicit per-run checklist snippet in this doc for repeatable schema validation commands.

---

## Run Log: `2026-03-15 18:03:17 +11:00` (Automation `schema-test`)

### Test Context Used

- Primary actor under test: resident student in University of Newcastle Student Living.
- Supporting assumptions only: Student Living admin acts as reception admin + triage/coordinator through the current `admin` role.
- Contractor assumptions only: contractor-organisation model remains the current dispatch path.

### New Edge-Case + Full JLC Tests Added

Added in [tests/test_app.py](../tests/test_app.py):

1. `test_admin_can_complete_job_while_clearing_assignment_in_same_update`
- What was tested: admin sends one patch request containing both `assigned_org_id: null` and `status: completed`.
- Result: accepted (`200`), job ends `completed` with no assignee.
- Why this matters for resident reporting: closure can occur without a responsible contractor, making completion accountability unclear to residents and Student Living coordinators.

2. `test_admin_can_reassign_job_while_in_progress_without_handoff_status`
- What was tested: admin reassigns a job after contractor has already set `in_progress`.
- Result: accepted (`200`), status stays `in_progress` while assignee changes.
- Why this matters for resident reporting: active-work ownership can switch without a visible handoff checkpoint, creating timeline ambiguity in the real JLC.

### JLC Findings From This Run

- Invariant gap confirmed: `completed` status currently does not require an assignee when assignment and status are changed together.
- Handoff gap confirmed: in-progress contractor ownership can be swapped without a dedicated handoff state/event type.
- Resident timeline remains chronological, but semantics are still free-text and cannot reliably distinguish execution ownership transitions.

### Refactor Suggestions (Mapped To This Run)

1. Enforce assignee-required completion invariant.
- Rule: reject transition to `completed` if both `assigned_org_id` and future direct-assignee fields are null.
- Benefit: prevents unowned closures and keeps resident-visible accountability intact.

2. Add explicit handoff workflow for in-progress reassignment.
- Introduce a transition/state such as `handoff_pending` or require `on_hold` before reassignment while active.
- Benefit: creates a coherent JLC checkpoint for Student Living triage/coordinator responsibilities.

3. Add typed event metadata for responsibility transfer.
- Add fields like `event_type=handoff`, `reason_code`, and `from_owner`/`to_owner`.
- Benefit: preserves resident-readable timeline while making role accountability queryable and auditable.

### Verification Status

- Code-level evidence: expanded with 2 additional edge-case tests above.
- Runtime execution in this environment: still blocked by Python startup failure (`ModuleNotFoundError: No module named 'encodings'`).

---

## Run Log: `2026-03-15 19:02:37 +11:00` (Automation `schema-test`)

### Test Context Used

- Primary actor under test: resident student in University of Newcastle Student Living.
- Supporting assumptions only: Student Living admin user is acting as reception admin + coordinator/triage officer through the single `admin` role.
- Contractor assumptions only: org-based contractor dispatch is the active path; independent contractor mode is still inferred as a required but unsupported operating mode.

### New Edge-Case + Full JLC Tests Added

Added in [tests/test_app.py](../tests/test_app.py):

1. `test_admin_can_close_unassigned_in_progress_job_after_contractor_loses_access`
- What was tested: resident report lifecycle where contractor starts work, admin clears assignment while job is `in_progress`, contractor then loses access, and admin closes as unassigned.
- Result: allowed; contractor gets `403`, admin can still mark `completed`, and job closes with `assigned_org_id = null`.
- Why it matters: creates an ownership void in the active/closure phases of the JLC that will confuse Student Living responsibility boundaries and resident accountability.

2. `test_single_admin_role_cannot_distinguish_reception_triage_and_coordinator_actions`
- What was tested: timeline identity semantics when one admin actor performs both routing and closure decisions.
- Result: all such events remain tagged as a single `admin` role and identical actor label.
- Why it matters: event history cannot distinguish reception vs triage vs coordinator responsibilities even though those are operationally distinct in Student Living.

Added in [tests/test_schema.py](../tests/test_schema.py):

3. `test_user_role_enum_remains_coarse_for_student_living_operational_responsibilities`
- What was tested: schema role surface for operational role granularity.
- Result: role enum remains only `resident`, `admin`, `contractor`.
- Why it matters: responsibility mapping required by Student Living operations is not modelled directly in schema contracts.

### JLC Findings From This Run

- Full straight-through path remains supported (`new -> assigned -> in_progress -> completed`) but ownership invariants are still weak.
- Mid-execution de-assignment still permits a terminal unassigned closure path, leaving no accountable contractor at completion.
- Responsibility trace remains coarse because all Student Living staff actions collapse under one `admin` identity in role and timeline data.

### Refactor Suggestions (Mapped To New Cases)

1. Add completion ownership invariant.
- Rule: reject `status=completed` when no assignee exists, unless an explicit triage override field/reason is present.
- Impact: prevents unowned closure outcomes seen in `test_admin_can_close_unassigned_in_progress_job_after_contractor_loses_access`.

2. Introduce Student Living capability separation.
- Add either explicit sub-roles (`reception_admin`, `triage_officer`, `coordinator`) or capability flags attached to admin users.
- Impact: resolves ambiguity proven by `test_single_admin_role_cannot_distinguish_reception_triage_and_coordinator_actions`.

3. Extend event schema with typed responsibility metadata.
- Add fields such as `event_type`, `responsibility_stage`, and `override_reason_code` for assignment and closure transitions.
- Impact: preserves resident-readable timeline while enabling audit and responsibility attribution.

4. Add explicit handoff checkpoint before closure after de-assignment.
- Require reassignment or a `handoff_pending`/`triage_review` state before a job can return to completion path.
- Impact: enforces coherent JLC when execution ownership changes mid-stream.

### Verification Status

- Code-level evidence: expanded with 3 additional tests listed above.
- Runtime execution: blocked in this environment due Python interpreter bootstrap failure (`ModuleNotFoundError: No module named 'encodings'`).

---

## Run Log: `2026-03-15 20:03:01 +11:00` (Automation `schema-test`)

### Test Context Used

- Primary actor under test: resident student in University of Newcastle Student Living.
- Supporting assumptions only: Student Living admin remains the combined reception + triage/coordinator actor under current `admin` role.
- Contractor assumptions only: mixed contractor modes are expected operationally, but current dispatch remains organisation-based.

### New Edge-Case + Full JLC Tests Added

Added in [tests/test_app.py](../tests/test_app.py):

1. `test_contractor_can_add_execution_note_after_completion_without_reopen_state`
- What was tested: contractor posts a new job event after the job is already marked `completed`.
- Result: allowed (`201`) while job status remains `completed`.
- Why this matters: completion is not terminal in timeline behavior, so resident-visible closure can still accumulate execution updates without a structured reopen/revisit branch.

Added in [tests/test_schema.py](../tests/test_schema.py):

2. `test_job_assignment_surface_is_org_only_for_contractor_dispatch`
- What was tested: assignment schema surface in the `jobs` table.
- Result: only `assigned_org_id` exists; no direct `assigned_user_id` equivalent is modelled.
- Why this matters: independent contractor dispatch remains unsupported at schema level, which conflicts with Student Living's mixed contractor operating model.

### JLC Findings From This Run

- Closure semantics remain incomplete: `completed` prevents status transitions but does not prevent additional contractor execution notes.
- Assignment semantics remain single-channel: jobs can only target contractor organisations, not independent contractor users directly.
- Resident timeline readability remains high, but accountability semantics remain ambiguous for post-completion activity.

### Refactor Suggestions (Mapped To New Cases)

1. Introduce a terminal-completion write policy.
- Rule: after `completed`, allow only typed closure-safe events (for example `resident_feedback`) unless status first moves to `reopened` or `follow_up_scheduled`.
- Impact: prevents unstructured contractor execution updates on closed jobs.

2. Add first-class direct contractor assignment support.
- Add `assigned_contractor_user_id` with mutual-exclusion rules against `assigned_org_id`.
- Impact: supports both independent and organisation-backed contractor dispatch.

3. Add explicit post-completion lifecycle branch.
- Add statuses such as `follow_up_scheduled` and `reopened`, with required reason codes.
- Impact: keeps resident-visible closure coherent while supporting real recurrence/revisit workflows.

### Verification Status

- Code-level evidence: expanded with 2 additional tests listed above.
- Runtime execution in this environment: blocked (`python` unavailable on PATH; `.venv\\Scripts\\python.exe` process launch denied `Access is denied`), so this run remains static/code-level verified.

---

## Run Log: `2026-03-15 21:02:55 +11:00` (Automation `schema-test`)

### Test Context Used

- Primary actor under test: resident student in University of Newcastle Student Living.
- Supporting assumptions only: Student Living admin acts as reception admin + coordinator/triage officer under the current single `admin` role.
- Contractor assumptions only: organisation-backed contractors and independent contractors remain expected operating modes.

### New Edge-Case + Full JLC Tests Added

Added in [tests/test_app.py](../tests/test_app.py):

1. `test_admin_can_move_assigned_job_to_in_progress_without_contractor_action`
- What was tested: admin marks a resident job `in_progress` immediately after assignment, without any contractor acknowledgement/event.
- Result: allowed (`200`) and timeline attributes the in-progress transition to admin.
- Why it matters: execution-stage ownership can appear to residents without contractor action, which blurs Student Living triage/coordinator vs contractor responsibilities.

Added in [tests/test_schema.py](../tests/test_schema.py):

2. `test_organisation_schema_cannot_represent_university_to_student_living_hierarchy`
- What was tested: organisation schema support for parent-child hierarchy (`University of Newcastle` parent with `Student Living` child org).
- Result: not represented; `organisations` has no `parent_org_id`/`root_org_id` fields.
- Why it matters: current model cannot encode the organisational context provided in this scenario, limiting policy/routing/reporting fidelity.

### JLC Findings From This Run

- Lifecycle responsibility remains incoherent for the execution phase: admins can move jobs into `in_progress` without contractor-side acceptance.
- Organisational context remains flattened: Student Living cannot be expressed as a child entity of University of Newcastle in schema.
- Resident-visible timeline remains chronological but not responsibility-safe for real handoff boundaries.

### Refactor Suggestions (Mapped To New Cases)

1. Require contractor acceptance before `in_progress`.
- Add a transition guard: admin may assign only; `in_progress` must be triggered by assigned contractor actor or explicit coordinator override with reason metadata.
- Impact: restores responsibility clarity between Student Living coordination and contractor execution.

2. Add organisation hierarchy fields.
- Extend `organisations` with `parent_org_id` (self-reference) and optional hierarchy traversal helpers.
- Impact: models `University of Newcastle -> Student Living` correctly for policy scoping, reporting, and future multi-org governance.

3. Add responsibility-stage metadata on events.
- Introduce typed event fields such as `event_type` and `responsibility_stage` (`reception`, `triage`, `coordination`, `execution`).
- Impact: preserves resident timeline readability while making accountability auditable.

### Verification Status

- Code-level evidence: expanded with 2 additional tests listed above.
- Runtime execution in this environment: blocked (`.venv\\Scripts\\python.exe` process launch denied with `Access is denied`), so this run remains static/code-level verified.

---

## Run Log: `2026-03-15 22:03:06 +11:00` (Automation `schema-test`)

### Test Context Used

- Primary actor under test: resident student in University of Newcastle Student Living.
- Supporting assumptions only: Student Living admin covers reception admin + coordinator/triage responsibilities via the current single `admin` role.
- Contractor assumptions only: contractor dispatch remains org-based, with maintenance teams and external contractors flattened into one contractor-org type.

### New Edge-Case + Full JLC Tests Added

Added in [tests/test_app.py](../tests/test_app.py):

1. `test_resident_full_jlc_timeline_lacks_typed_responsibility_stage_metadata`
- What was tested: full resident-visible JLC (`new -> assigned -> in_progress -> completed`) with assignment by admin, progress by admin, completion by contractor.
- Result: lifecycle events are recorded, but event payload contains no typed `responsibility_stage` metadata.
- Why it matters: resident can see chronology but cannot distinguish reception/triage/coordination vs execution ownership stages in a structured way.

Added in [tests/test_schema.py](../tests/test_schema.py):

2. `test_organisation_type_enum_cannot_distinguish_maintenance_team_from_external_contractor_org`
- What was tested: contractor organisation typing granularity.
- Result: enum surface remains `{university, contractor}` only.
- Why it matters: Student Living cannot model contractor mode distinctions (internal maintenance team vs external contractor org) for routing/policy/reporting.

3. `test_user_schema_lacks_student_living_operational_responsibility_fields`
- What was tested: user schema surface for operational responsibility markers.
- Result: no `responsibility_stage` / `capability_flags` fields exist.
- Why it matters: current schema cannot encode reception admin vs triage officer vs coordinator responsibilities directly.

### JLC Findings From This Run

- Full resident lifecycle remains operable, but responsibility semantics are still implicit in free-text events.
- Contractor organisation modelling remains too coarse for the stated Student Living operating context.
- Student Living internal responsibility boundaries remain unmodelled at user-schema level.

### Refactor Suggestions (Mapped To This Run)

1. Add typed responsibility-stage metadata to events.
- Add fields such as `event_type` and `responsibility_stage` (`reception`, `triage`, `coordination`, `execution`).
- Impact: keeps resident timeline readable while making accountability queryable.

2. Expand organisation type modelling for contractor modes.
- Introduce contractor subtyping or an explicit `contractor_mode` field to differentiate maintenance teams from external contractor organisations.
- Impact: improves dispatch policy precision and reporting in Student Living operations.

3. Model Student Living admin capability boundaries.
- Add user-level capability fields (or role extensions) for reception admin, triage officer, and coordinator responsibilities.
- Impact: reduces responsibility ambiguity during handoff and closure decisions.

### Verification Status

- Code-level evidence: expanded with 3 additional tests listed above.
- Runtime execution in this environment: blocked (`.venv\\Scripts\\python.exe` launch denied with `Access is denied`), so this run remains static/code-level verified.
