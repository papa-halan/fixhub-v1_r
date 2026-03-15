# Schema Test: UoN Student Living Resident Reporting

Date: `2026-03-15 17:30:56 +11:00`
Scope: code-level schema and workflow validation in [app/models/mvp.py](../app/models/mvp.py), [app/models/enums.py](../app/models/enums.py), [app/main.py](../app/main.py), [app/services/demo.py](../app/services/demo.py), and [tests/test_app.py](../tests/test_app.py).

## Implemented Baseline (Current State)

- Core entities remain: `organisations`, `users`, `jobs`, `events`.
- User roles remain: `resident`, `admin`, `contractor`.
- Organisation types remain: `university`, `contractor`.
- Job statuses remain: `new`, `assigned`, `in_progress`, `completed`.
- Effective lifecycle remains linear dispatch with event timeline evidence.
- Browser access now requires an explicit demo-user sign-in instead of a default resident fallback.

## Implemented Changes Observed In This Run

- `DATABASE_URL` default in [app/core/config.py](../app/core/config.py) now targets PostgreSQL instead of SQLite.
- UI forms now declare `method="post"` in:
- [app/templates/resident_report.html](../app/templates/resident_report.html)
- [app/templates/admin_job.html](../app/templates/admin_job.html)
- [app/templates/contractor_job.html](../app/templates/contractor_job.html)
- base template script loading changed in [app/templates/base.html](../app/templates/base.html) to non-deferred script include.
- coverage added in [tests/test_app.py](../tests/test_app.py): `test_report_page_wires_post_form`.

## Validation Evidence

- Structural evidence: schema footprint in tests still asserts exactly four tables (`events`, `jobs`, `organisations`, `users`).
- Workflow evidence: resident-admin-contractor flow still validates assignment, event creation, and status progression.
- Runtime execution in this environment: full pytest execution remains blocked by Python startup error (`ModuleNotFoundError: No module named 'encodings'`) as previously observed; code-level assertions were used as evidence.

## Resident-Centric Suitability Summary

- Intake creation and timeline visibility: pass.
- Assignment visibility and contractor updates: pass.
- Multi-trade dispatch, blocked states, reopen/escalation semantics: not implemented in current schema.
- Fine-grained Student Living role boundaries: not implemented in current role model.

## SD Documentation Practice Sanity Check

- Facts vs proposals separation: pass (this document now separates implemented and TODO).
- Source traceability to code/tests: pass (all current-state claims mapped to repository files).
- Portability for sharing: pass (repository-relative links; no machine-specific paths).
- Verification depth: partial (runtime test execution not available in this environment).

## Feedback On Documentation Process (Against Standard SD Practice)

- Positive: implemented-state logging is now explicit and timestamped, reducing ambiguity.
- Positive: docs now include a dedicated changelog and index, improving discoverability.
- Gap: runtime verification evidence should be attached per run once environment issues are fixed.
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
