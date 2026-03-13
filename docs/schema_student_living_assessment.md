# Schema Test: UoN Student Living Resident Workflow

| Metadata | Value |
| --- | --- |
| Docs version | 0.2.0 |
| Status | Active |
| Owner | Domain documentation maintainer |
| Reviewers | Project maintainer; architecture maintainer |
| Last updated | 2026-03-13 |
| Review cadence | On change and quarterly |

Date: 2026-03-13 (Australia/Sydney)
Scope: Resident-reported maintenance workflow for the full job life cycle (JLC), including edge cases and role clarity.
Method: Static schema + service behavior test against current implementation.
Execution note: This assessment remains static-analysis only; no runtime verification was performed as part of this document revision.

## Context Under Test

- Primary actor for testing: resident user (student at University of Newcastle Student Living).
- Assumed non-resident validation actor: `staff` user acting as reception admin + coordinator/triage officer.
- Assumed non-resident validation actors: `contractor` users representing internal maintenance team members, independent contractors, and contractor organizations.
- Organisation context: Student Living under University of Newcastle.

## Baseline Schema/Service Constraints

- Roles are coarse: `resident`, `staff`, `contractor`.
- Work order statuses are linear only: `assigned -> in_progress -> completed`.
- Routing is single-target: one enabled `(residence_id, category) -> contractor_user_id`.
- Request to work order cardinality is strict 1:1 (`uq_work_orders_request_id`).

References:
- [`app/models/enums.py`](../app/models/enums.py)
- [`app/models/mvp.py`](../app/models/mvp.py)
- [`app/services/maintenance_coordination.py`](../app/services/maintenance_coordination.py)
- [`app/services/policy.py`](../app/services/policy.py)
- [`app/services/routing.py`](../app/services/routing.py)

## Full JLC Test Matrix (Resident-Centric)

1. JLC-01 Resident submits issue in own org
- Expected: request persists, event emitted, actor traceable.
- Actual: Pass.
- Explanation: `submit_maintenance_request` validates resident role/org and emits `uon.maintenance_request.submitted`.

2. JLC-02 Resident sees pre-dispatch lifecycle state
- Expected: resident can distinguish submitted vs triaged vs awaiting assignment.
- Actual: Fail (schema gap).
- Explanation: request has no status field; resident only sees request plus optional work order.

3. JLC-03 Resident can identify who currently owns triage
- Expected: visible/traceable team ownership (reception vs triage coordinator).
- Actual: Fail (responsibility gap).
- Explanation: no triage ownership fields (`triaged_by`, `assigned_staff`, etc.); single `staff` role collapses responsibilities.

4. JLC-04 Staff dispatches via routing rule
- Expected: deterministic dispatch from category/residence mapping.
- Actual: Pass (MVP behavior).
- Explanation: dispatch resolves contractor via `lookup_contractor_user_id` then creates work order + integration job.

5. JLC-05 Staff dispatch override to named contractor
- Expected: override with accountability metadata.
- Actual: Partial.
- Explanation: override exists (`contractor_user_id_override`) but no mandatory reason fields for audit/reporting quality.

6. JLC-06 Contractor starts assigned job
- Expected: only assigned contractor can progress status.
- Actual: Pass.
- Explanation: `require_assigned_contractor` enforces ownership before status transition.

7. JLC-07 Contractor completes job and resident sees closure semantics
- Expected: completion state plus resident-facing confirmation/acknowledgement.
- Actual: Partial.
- Explanation: completion transition exists, but resident acknowledgement/acceptance state is not modeled.

8. JLC-08 Resident issue requires cancellation/rejection before dispatch
- Expected: request can be cancelled/rejected with clear reason.
- Actual: Fail.
- Explanation: no request status machine; only creation is modeled pre-dispatch.

9. JLC-09 Resident issue becomes on-hold/revisit after dispatch
- Expected: operational states such as `on_hold`, `failed_access`, `reassigned`.
- Actual: Fail.
- Explanation: work order enum supports only three states; no operational branch states.

10. JLC-10 Resident issue requires multi-trade split (e.g., plumbing + electrical)
- Expected: one request may fan out to multiple work orders.
- Actual: Fail.
- Explanation: unique constraint on `work_orders.request_id` enforces hard 1:1.

11. JLC-11 Routing rule missing for resident category
- Expected: triage backlog or manual assignment queue instead of hard dead-end.
- Actual: Fail.
- Explanation: missing rule raises `RoutingRuleNotFoundError`; no modeled fallback state/path.

12. JLC-12 Cross-org access isolation for resident-facing data
- Expected: actor isolation by org and ownership.
- Actual: Pass (basic).
- Explanation: policy checks enforce role + org alignment and resident ownership checks.

## Edge Cases and Explanations

1. Contractor archetype ambiguity
- Case: internal team, independent, and contractor-org workers need distinct handling.
- Current behavior: all represented as `UserRole.contractor`.
- Why it matters: no reliable policy/reporting split by contractor source model.

2. Student Living internal responsibility ambiguity
- Case: reception admin and triage coordinator are different responsibilities.
- Current behavior: both are `staff` with no explicit duty boundary.
- Why it matters: accountability and handoff ownership are not first-class; likely operational confusion.

3. Manual dispatch without routing coverage
- Case: resident submits uncommon category with no configured route.
- Current behavior: dispatch path fails hard.
- Why it matters: user-facing lifecycle appears stalled with no defined exception path.

4. Reassignment after contractor decline/no-show
- Case: assigned contractor cannot perform task.
- Current behavior: no reassignment state/event contract.
- Why it matters: real lifecycle branch missing from schema.

5. Resident completion dispute
- Case: resident reports job incomplete after contractor marks complete.
- Current behavior: no reopen/dispute state.
- Why it matters: lifecycle terminates too early for real operations.

## Incoherence Against Real Job Lifecycle

- The schema models a clean happy path but not the operational branches common in Student Living operations.
- Resident-visible lifecycle is under-modeled before dispatch and after nominal completion.
- Staff accountability is abstracted into one role, so reception/triage/coordinator ownership is not explicit.
- Contractor sourcing variants are flattened, reducing policy precision and reporting quality.

## Refactor Suggestions

1. Add `maintenance_requests` lifecycle state machine
- Add `status` with at least: `submitted`, `triaged`, `awaiting_assignment`, `dispatched`, `cancelled`, `rejected`.
- Add ownership/audit fields: `triaged_by_user_id`, `triaged_at`, `triage_reason`.

2. Separate Student Living staff responsibilities
- Introduce role-capability mapping (preferred) or scoped staff role set:
- `reception_admin`, `triage_officer`, `coordinator`.
- Record assignment transitions per request.

3. Model contractor identity beyond role enum
- Add `contractor_profiles` with `contractor_type` (`internal_team`, `independent`, `org_member`).
- Add `contractor_orgs` and optional profile linkage.

4. Expand work order lifecycle
- Extend statuses: `accepted`, `on_hold`, `reassigned`, `cancelled`, `failed_access`.
- Add `status_reason`, `status_note`, `reassigned_from_work_order_id` where relevant.

5. Improve routing resilience
- Replace single rule target with priority/fallback candidates.
- Persist dispatch provenance (`dispatch_mode`, `dispatch_reason`, `dispatch_rule_id`).

6. Support request splitting when required
- Replace strict 1:1 with 1:N (`request_work_order_links` or remove unique `request_id` in work orders).

7. Add resident closure semantics
- Add post-completion resident outcome states (for example: `completed_pending_resident_ack`, `reopened`).

## Recommended Implementation Order

1. Request lifecycle + triage ownership fields.
2. Staff role-capability and responsibility boundaries.
3. Work order lifecycle expansion + reassignment semantics.
4. Contractor profile/org model.
5. Routing fallback model.
6. Multi-work-order split support.
7. Resident acknowledgement/reopen flow.

## Change Log

- 2026-03-13 15:52:00 +11:00 (Australia/Sydney): Added document metadata and converted source links to repository-relative paths for portability.
