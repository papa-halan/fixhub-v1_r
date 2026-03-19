# Schema Assessment: Student Living Workflow

Date: `2026-03-19 15:24:12 +11:00`

## Document Metadata

- Owner: `student-living-platform`
- Reviewer: `schema-test-automation`
- Status: `active`

## Implemented Baseline

- `JobStatus` now covers `new`, `assigned`, `triaged`, `scheduled`, `in_progress`, `on_hold`, `blocked`, `completed`, `cancelled`, `reopened`, `follow_up_scheduled`, and `escalated`
- assignment is decoupled from status via mutually exclusive `assigned_org_id` and `assigned_contractor_user_id`
- event records now store `event_type`, `reason_code`, `responsibility_stage`, and `owner_scope`
- workflow/status-transition rules now live in `app/services/workflow.py`, keeping the API layer focused on transport concerns
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
| accountability requirement | branch states such as `on_hold`, `blocked`, `reopened`, `follow_up_scheduled`, and `escalated` require `reason_code`; `completed` requires an explicit `reason_code` or `responsibility_stage` |

## Verification Evidence

- required runtime verification command: `.\.venv\Scripts\python.exe -m pytest tests\test_schema.py tests\test_app.py`
- current run execution status: verified locally in this environment
- latest recorded successful result in this run: `23 passed`
- additional verification in this run: `.\.venv\Scripts\python.exe -m ruff check app tests` passed cleanly
- runtime coverage in this run now includes lifecycle progression, direct contractor assignment, assignment rollback invariants, role gating, blocked/on-hold/reopen branches, and explicit completion-accountability enforcement

## Remaining TODO (Proposed)

- split resident request from execution work order if one resident issue must spawn multiple contractor tracks
- add a first-class visit/appointment entity instead of representing scheduling only as status plus timeline events
- decide whether the legacy `admin` umbrella role should remain long term or be fully replaced by capability-style permissions

## Run Log: `2026-03-19 15:24:12 +11:00`

### Delivered In This Run

- extracted workflow/state-machine helpers into `app/services/workflow.py`
- moved API consumers onto the workflow service for transition guards, event defaults, and assignment fallback behavior
- tightened completion accountability so `completed` now requires explicit `reason_code` or `responsibility_stage`
- updated the operations and contractor pages so prompted reason codes can be supplied for guarded transitions, and contractor completion sends `responsibility_stage=execution`
- expanded app tests for `blocked`, `on_hold`, `reopened`, and explicit completion-accountability paths
- verified the focused schema/app suite and lint checks in this environment

### Outcome

- the refined Student Living workflow is now implemented with a dedicated workflow service layer, stronger accountability on completion, and broader executable regression coverage
- this workspace still contains older dirty-worktree documentation entries with later timestamps than the current environment clock; the timestamp above reflects the actual runtime-verification session for this pass

## Run Log: `2026-03-19 15:12:17 +11:00`

### Delivered In This Run

- scanned commits since automation `Last run: 2026-03-19T04:00:56.070Z`.
- reviewed concrete commit evidence:
  - `9c0a0b5397318d6d2a97774ade77e73de0ed0482`
  - `f7877bd00ca0e4837f82db0364d73bcde83310ab`
- validated resident-reported problem flow coverage by test intent review (`create -> assign -> triage -> schedule -> in_progress -> completed`) and edge cases (direct independent contractor dispatch, assignment clear rollback, role gating, follow-up reason requirements, mutual exclusivity guards).
- updated documentation logs only; no README diagram changes were needed in this run.

### Outcome

- no additional minimal fix was applied because commit diffs did not provide strong concrete evidence of a new regression beyond the already-landed assignment-detail correction.
- product TODO tracks `A2`, `A3`, and `A4` remain open and require implementation work plus executable runtime validation in an environment where `python -m pytest` can run.

## Run Log: `2026-03-19 17:20:00 +11:00`

### Delivered In This Run

- extended the lifecycle with triage, scheduling, follow-up, and escalation states
- introduced direct contractor dispatch and assignee invariants
- added structured event metadata and organisation hierarchy
- refreshed README and architecture docs with simplified lifecycle visuals and concrete API examples
- added Alembic migration `20260319_0005_operational_workflow_refactor.py`

### Outcome

The resident-admin-contractor workflow now better matches a realistic Student Living operating model while preserving the newer location/asset foundation added earlier in the repository.

## Run Log: `2026-03-19 15:04:12 +11:00`

### Delivered In This Run

- scanned commits since last automation run (`2026-03-19T03:31:31.650Z`) and in the last 24 hours.
- confirmed there are no new commits since the last run; latest 24h commit remains `dcef84a5c27b2f611e9f0ccfca4777109e4c7d87`.
- applied a minimal workflow consistency fix in `app/api/jobs.py`: permission error text now states `Only coordinators or admins can change assignment`, matching actual role checks.

### Verification Status

- attempted required runtime flow:
  - `python -m pip install -e .[dev]`
  - `python -m pytest --version`
  - `python -m pytest`
- execution is blocked in this environment (`python`/`py` unavailable and `.venv\\Scripts\\python.exe` cannot be executed due access denied), so this run is static/code-evidence verified only.
