# Schema Assessment: Student Living Workflow

Date: `2026-03-22 17:15:11 +11:00`

## Document Metadata

- Owner: `student-living-platform`
- Reviewer: `schema-test-automation`
- Status: `active`

## Implemented Baseline

- `JobStatus` covers `new`, `assigned`, `triaged`, `scheduled`, `in_progress`, `on_hold`, `blocked`, `completed`, `cancelled`, `reopened`, `follow_up_scheduled`, and `escalated`
- assignment is decoupled from status via mutually exclusive `assigned_org_id` and `assigned_contractor_user_id`
- event records store `event_type`, `reason_code`, `responsibility_stage`, and `owner_scope`
- workflow/status-transition rules live in `app/services/workflow.py`
- operations roles are split across `reception_admin`, `triage_officer`, and `coordinator`
- users authenticate via password login plus signed session cookies
- demo shortcuts are rendered only when `demo_mode` is enabled
- seeded demo accounts can also authenticate in normal mode when `FIXHUB_SEED_DEMO_DATA=1`, but shortcut switching stays demo-only
- normal mode supports an optional bootstrap non-demo user through startup environment variables
- runtime startup requires the database to be at Alembic head before serving traffic
- locations support `parent_id` and `type`, and resident report creation uses structured `location_id`
- jobs store `organisation_id` directly and keep `location_detail_text` as descriptive context only
- root-level legacy placeholder locations are removed or demoted out of the active catalog during migration cleanup

## Workflow Suitability Summary

### What is supported now

- explicit intake, triage, scheduling, and execution checkpoints before completion
- blocked, on-hold, escalation, reopen, and follow-up paths
- direct independent-contractor dispatch
- role-gated triage and scheduling actions
- resident-visible timelines with structured accountability metadata
- organisation-scoped resident reporting with managed location selection
- explicit demo-mode auth containment for seeded demo accounts and shortcut switching

### Role Semantics In The Current UI

- `resident`: submits and tracks their own reports
- `reception_admin`: front desk / intake role for note-taking and clarification
- `triage_officer`: property manager role for triage and scheduling
- `coordinator`: dispatch coordinator role for assignment and operational rerouting
- `contractor`: contractor or maintenance technician role for execution updates
- `admin`: system admin role kept for bootstrap/demo/admin oversight

### Guard Conditions

| Guard | Implemented behavior |
| --- | --- |
| assignee required | `assigned`, `scheduled`, `in_progress`, `blocked`, `completed`, and `follow_up_scheduled` reject missing-assignee transitions |
| assignment clear rollback | clearing the last assignee without an explicit status change rolls the job back to `new` or `triaged` |
| assignment exclusivity | org assignment and direct contractor assignment cannot both be present |
| triage permissions | only `triage_officer` or `admin` can move jobs to `triaged`, `scheduled`, or `follow_up_scheduled` |
| coordination permissions | only `coordinator` or `admin` can change dispatch targets |
| contractor execution scope | contractors can move work through execution states but cannot place jobs on hold from the UI |
| accountability requirement | branch states such as `on_hold`, `blocked`, `reopened`, `follow_up_scheduled`, and `escalated` require `reason_code`; `completed` requires explicit accountability metadata |
| structured location validation | report creation requires an org-scoped, managed child `space` or `unit` location |

## Verification Evidence

- required runtime verification command: `.\.venv\Scripts\python.exe -m pytest tests\test_schema.py tests\test_migrations.py tests\test_app.py -q`
- current run execution status: verified locally in this environment
- latest recorded successful result in this pass: `33 passed`
- runtime coverage in this pass includes migration bootstrap and round-trip smoke, placeholder-location cleanup, startup schema enforcement, browser login behavior, demo gating, org boundary checks, location validation, lifecycle progression, direct contractor assignment, assignment rollback invariants, role gating, follow-up rules, note-only event creation, and role-appropriate UI controls

## Remaining Risks

- downgrade behavior is still best treated as smoke coverage rather than perfect historical rollback
- assets remain lightweight and name-driven; they are more structured than before but not yet a governed asset registry
- the current model still uses `Job` as the single operational object until the later Phase 1 split

## Deferred For Phase 1

- request -> work-order split
- structured visit/dispatch records
- richer routing-decision persistence
- public reporting, councils/homeowners, GIS/maps, and ownership verification flows
- full RBAC, invites, password reset, or enterprise auth
# Student Living Schema Assessment

## 2026-04-04 adjustment

The repo now treats `assets` as optional catalog data rather than something that can be truthfully derived from arbitrary resident text at report time.

This is a better fit for the current pilot because:

- resident reports reliably know the location more often than the exact maintainable asset
- free-text asset creation inflated the apparent quality of structured data
- optional asset linkage preserves the credible pilot path without pretending the asset register is authoritative yet
