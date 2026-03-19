# Schema Assessment: Student Living Workflow

Date: `2026-03-19 17:20:00 +11:00`

## Document Metadata

- Owner: `student-living-platform`
- Reviewer: `schema-test-automation`
- Status: `active`

## Implemented Baseline

- `JobStatus` now covers `new`, `assigned`, `triaged`, `scheduled`, `in_progress`, `on_hold`, `blocked`, `completed`, `cancelled`, `reopened`, `follow_up_scheduled`, and `escalated`
- assignment is decoupled from status via mutually exclusive `assigned_org_id` and `assigned_contractor_user_id`
- event records now store `event_type`, `reason_code`, `responsibility_stage`, and `owner_scope`
- operations roles now include `reception_admin`, `triage_officer`, and `coordinator`
- organisations support `parent_org_id` and optional `contractor_mode`
- seeded data now models `University of Newcastle -> Student Living` plus both external and maintenance contractor modes

## Workflow Suitability Summary

### What is now supported

- explicit triage and scheduling checkpoints before execution
- blocked/on-hold/escalation/reopen/follow-up paths
- direct independent-contractor dispatch
- role-gated triage and scheduling actions
- resident-visible timelines with structured accountability metadata

### Guard Conditions

| Guard | Implemented behavior |
| --- | --- |
| assignee required | `assigned`, `scheduled`, `in_progress`, `blocked`, `completed`, and `follow_up_scheduled` reject missing-assignee transitions |
| assignment clear rollback | clearing the last assignee without an explicit status change rolls the job back to `new` or `triaged` |
| assignment exclusivity | org assignment and direct contractor assignment cannot both be present |
| triage permissions | only `triage_officer` or `admin` can move jobs to `triaged`, `scheduled`, or `follow_up_scheduled` |
| coordination permissions | only `coordinator` or `admin` can change assignment, reopen, escalate, or cancel |
| accountability requirement | branch states such as `on_hold`, `blocked`, `reopened`, `follow_up_scheduled`, and `escalated` require `reason_code` |

## Verification Evidence

- runtime verification command: `python -m pytest tests\test_schema.py tests\test_app.py`
- result in this environment: `20 passed`
- coverage now includes lifecycle progression, direct contractor assignment, assignment rollback invariants, role gating, and structured event metadata

## Remaining TODO (Proposed)

- split resident request from execution work order if one resident issue must spawn multiple contractor tracks
- add a first-class visit/appointment entity instead of representing scheduling only as status plus timeline events
- decide whether the legacy `admin` umbrella role should remain long term or be fully replaced by capability-style permissions

## Run Log: `2026-03-19 17:20:00 +11:00`

### Delivered In This Run

- extended the lifecycle with triage, scheduling, follow-up, and escalation states
- introduced direct contractor dispatch and assignee invariants
- added structured event metadata and organisation hierarchy
- refreshed README and architecture docs with simplified lifecycle visuals and concrete API examples
- added Alembic migration `20260319_0005_operational_workflow_refactor.py`

### Outcome

The resident-admin-contractor workflow now better matches a realistic Student Living operating model while preserving the newer location/asset foundation added earlier in the repository.
