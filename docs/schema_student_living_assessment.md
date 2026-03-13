# Schema Test: UoN Student Living Resident Reporting

Date: 2026-03-13
Scope: Code-level schema and workflow validation in [app/models/mvp.py](/C:/Users/halan/PycharmProjects/fixhub-v1/app/models/mvp.py), [app/models/enums.py](/C:/Users/halan/PycharmProjects/fixhub-v1/app/models/enums.py), [app/main.py](/C:/Users/halan/PycharmProjects/fixhub-v1/app/main.py), and [app/services/demo.py](/C:/Users/halan/PycharmProjects/fixhub-v1/app/services/demo.py).
Runtime validation in this run: test execution attempted with `.venv\Scripts\pytest.exe tests\test_app.py -q` and `.venv\Scripts\python.exe -m pytest tests\test_app.py -q`, both failed before test collection with `ModuleNotFoundError: No module named 'encodings'`.

## Test Lens and Assumptions
- Primary testing actor (only direct actor in cases): student resident in University of Newcastle Student Living.
- Assumed-only actors: Student Living admin triage/coordinator user, reception admin, and contractor user.
- Contractor archetypes expected in real ops:
- maintenance team,
- independent contractor,
- contractor user inside a contractor organisation.
- Org context expected: Student Living is a sub-unit within University of Newcastle.

## Current Schema Snapshot
- Core entities: `organisations`, `users`, `jobs`, `events`.
- User roles: `resident`, `admin`, `contractor`.
- Organisation types: `university`, `contractor`.
- Job statuses: `new`, `assigned`, `in_progress`, `completed`.
- Effective lifecycle: linear dispatch pipeline with free-text event trail.

## Evidence for This Run
- Structural schema evidence: table model remains 4-table core (`organisations`, `users`, `jobs`, `events`) as defined in [app/models/mvp.py](/C:/Users/halan/PycharmProjects/fixhub-v1/app/models/mvp.py).
- Workflow evidence: transition rules still constrained by `ALLOWED_STATUS_CHANGES` in [app/main.py](/C:/Users/halan/PycharmProjects/fixhub-v1/app/main.py), with no blocked/reopen/escalation states.
- Actor lens compliance: resident remains the only direct actor in all test cases; admin and contractor behavior is treated as assumed operational context.
- Runtime note: API behavior assertions in [tests/test_app.py](/C:/Users/halan/PycharmProjects/fixhub-v1/tests/test_app.py) were used as code-level evidence because runtime execution failed in this environment.

## Full JLC Test Matrix (Resident-Centric)

1. Intake creation by resident
- Resident action: submit a maintenance problem.
- Expected in real JLC: intake enters Student Living queue with triage responsibility.
- Actual model behavior: creates one `jobs` row in `new`, emits `Report created`.
- Result: Partial.
- Explanation: intake exists, but no explicit queue ownership (`triage_owner`) or routing state.

2. Reception quality check and categorization
- Resident action: waits after submission.
- Expected: issue category, severity, and contact validation before dispatch.
- Actual: no category/severity fields or validation stage state.
- Result: Fail.
- Explanation: required triage data must be improvised in free text.

3. Duplicate/related request handling
- Resident action: submits repeat report for same location/fault.
- Expected: duplicate linking or merge with resident-visible note.
- Actual: each report remains standalone with no relation keys.
- Result: Fail.
- Explanation: schema has no request linkage entity.

4. Responsibility clarity inside Student Living
- Resident action: tracks "who owns my issue right now?"
- Expected: distinct reception admin, triage officer, coordinator ownership at each phase.
- Actual: all staff functions collapse into one `admin` role.
- Result: Fail.
- Explanation: role granularity is too coarse for accountability and handoff clarity.

5. Contractor sourcing mode selection
- Resident action: expects assignment to best-fit contractor type.
- Expected: dispatch decision among maintenance team, independent contractor, or contractor-org member.
- Actual: assignable target is only `Organisation(type=contractor)`.
- Result: Fail.
- Explanation: independent and internal team archetypes are not modeled natively.

6. Assignment confirmation and notification
- Resident action: expects transparent assignment update.
- Expected: structured assignment event with source team and rationale.
- Actual: event message supports "Assigned/Reassigned <org>" text only.
- Result: Partial.
- Explanation: there is a visible trail, but no structured reason code or dispatch rationale.

7. Scheduling and appointment commitment
- Resident action: wants appointment window and updates.
- Expected: queryable visit window, no-access handling, ETA revisions.
- Actual: only free-text events can convey scheduling.
- Result: Fail.
- Explanation: appointment data is not first-class, so SLA reporting is unreliable.

8. Work execution start
- Resident action: sees issue move to active work.
- Expected: in-progress transition with accountable crew/technician identity.
- Actual: contractor can move to `in_progress`; actor is user/org only.
- Result: Partial.
- Explanation: progress state exists, but no per-visit performer structure.

9. Blocked/on-hold handling
- Resident action: receives "awaiting parts" update.
- Expected: explicit blocked state + reason + revised ETA.
- Actual: no blocked state; only narrative event text.
- Result: Fail.
- Explanation: lifecycle cannot represent stalled work in a controlled way.

10. Multi-trade split execution
- Resident action: one report requires multiple specialist actions.
- Expected: one resident request with multiple linked work orders.
- Actual: single `jobs` record with one assigned org at a time.
- Result: Fail.
- Explanation: 1:1 request/work shape is incompatible with realistic split jobs.

11. Completion, verification, and reopen
- Resident action: verifies outcome and reopens if unresolved.
- Expected: resident acceptance gate before closure, reopen path if failed fix.
- Actual: contractor/admin can set `completed`; resident cannot transition status.
- Result: Fail.
- Explanation: no resident acceptance or defect loop.

12. Misrouting and escalation
- Resident action: wrong team or unresolved job requires escalation.
- Expected: reroute state, escalation owner, and complaint tracking.
- Actual: manual reassignment only, no escalation state machine.
- Result: Fail.
- Explanation: workflow has no first-class reroute/escalation model.

## Edge Cases and Outcomes
1. Independent contractor without organisation
- Observed from logic: contractor job visibility requires `organisation_id`.
- Outcome: independent contractor actor cannot work jobs unless forced into org construct.
- Impact: real contractor archetypes are blocked by schema constraints.

2. Assignment cleared mid-flow
- Observed from logic: clearing assignment can push `assigned -> new` automatically.
- Outcome: lifecycle appears to move backward without explicit triage/routing semantics.
- Impact: resident-facing timeline becomes hard to interpret.

3. Terminal completion without resident authority
- Observed from logic: `completed` is terminal and resident cannot change status.
- Outcome: unresolved issues after completion require off-record handling.
- Impact: hidden operational workload and complaint leakage.

4. Student Living ownership ambiguity
- Observed from role model: no distinction among reception, triage, coordinator.
- Outcome: "admin did X" appears in audit trail regardless of responsibility boundary.
- Impact: weak accountability and handoff confusion.

5. Student Living vs University hierarchy visibility
- Observed from schema: `organisations` has no parent/child structure and only one `type` enum.
- Outcome: Student Living cannot be represented as a formal sub-org of University of Newcastle.
- Impact: routing policies, reporting scope, and authority boundaries are hard-coded instead of data-driven.

## Refactor Suggestions (Prioritized)
1. Introduce explicit request lifecycle state machine
- Add request states: `submitted`, `triage`, `awaiting_assignment`, `scheduled`, `in_progress`, `blocked`, `pending_resident_confirmation`, `closed`, `reopened`, `escalated`.
- Reason: aligns model to real Student Living JLC and removes hidden transitions.

2. Split resident request from execution work
- Create `maintenance_requests` (resident-facing) and `work_orders` (dispatch-facing), with 1:N request->work_orders.
- Reason: supports multi-trade, phased, and repeated visits.

3. Model Student Living responsibility roles explicitly
- Add staff role variants: `reception_admin`, `triage_officer`, `coordinator`.
- Add ownership fields and SLA timestamps at request/work order levels.
- Reason: resolves accountability confusion and supports operational reporting.

4. Add contractor archetype support
- Add contractor profile classification: `maintenance_team`, `independent`, `org_member`.
- Keep optional org linkage for independents, mandatory where needed.
- Reason: aligns data model to the contractor forms described in scope.

5. Add structured routing and escalation records
- Add routing decisions, reason codes, escalation records, decision actor, and timestamps.
- Reason: makes reroute/escalation visible, auditable, and reportable.

6. Add structured appointment/visit entities
- Add visit windows, attendance, access-failure reasons, and outcomes.
- Reason: supports resident communication and SLA reliability.

7. Add resident confirmation gate
- Add explicit resident confirmation state/action and reopen endpoint.
- Reason: makes closure quality-controlled from the resident perspective.

8. Add organisation hierarchy for governance context
- Add parent-child organisation links (for example: University of Newcastle -> Student Living).
- Reason: enables scoped triage authority, reporting rollups, and policy inheritance without custom logic.

## Explanatory Mapping: Why Current Workflow Feels Incomplete
- Incoherent job lifecycle: lifecycle transitions are present but too narrow for real operations (`new -> assigned -> in_progress -> completed` only).
- Over-abstracted data model: one `admin` role and one contractor org type hide practical responsibility and sourcing decisions.
- Responsibility confusion risk: Student Living staff boundaries are not represented, so triage/coordinator ownership is implicit instead of explicit.

## Next Validation Pack (Post-Refactor)
1. Resident submission enters `triage` with named triage owner and SLA clock.
2. Coordinator creates two work orders under one request (maintenance + specialist).
3. One work order transitions to `blocked` with parts ETA while other proceeds.
4. Resident rejects first completion, request reopens, escalation is recorded.
5. Independent contractor completes assigned work order without organisation lockout.
6. Misrouted request is rerouted with preserved accountability chain and resident-visible updates.
