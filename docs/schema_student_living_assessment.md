# Schema Assessment: Residence Operations Pilot

Date: `2026-04-10 15:42:17 +10:00`

## Document Metadata

- Owner: `fixhub-pilot`
- Reviewer: `schema-test-automation`
- Status: `active`

## Implemented Baseline

- `JobStatus` covers `new`, `assigned`, `triaged`, `scheduled`, `in_progress`, `on_hold`, `blocked`, `completed`, `cancelled`, `reopened`, `follow_up_scheduled`, and `escalated`
- assignment is decoupled from status, and named-contractor dispatch now preserves both `assigned_org_id` and `assigned_contractor_user_id`
- event records store `event_type`, `target_status`, `reason_code`, `responsibility_stage`, `owner_scope`, and assignment-target snapshots
- `report_created` events now also carry a structured intake-channel `reason_code`, so the record can distinguish resident portal, staff-created, after-hours, and inspection-origin entry paths without inventing a second intake table yet
- note-only events now recognize explicit handoff and post-visit accountability reason codes such as `after_hours_handoff_received`, `liability_assessed`, `charge_notice_issued`, and `charge_resolved`
- workflow/status-transition rules live in `app/services/workflow.py`
- operations roles are split across `reception_admin`, `triage_officer`, and `coordinator`
- users authenticate via password login plus signed session cookies
- demo shortcuts are rendered only when `demo_mode` is enabled
- seeded demo accounts can also authenticate in normal mode when `FIXHUB_SEED_DEMO_DATA=1`, but shortcut switching stays demo-only
- normal mode supports an optional bootstrap non-demo user through startup environment variables
- runtime startup requires the database to be at Alembic head before serving traffic
- locations support `parent_id` and `type`, and resident report creation uses structured `location_id`
- resident location selection and job reads now preserve the full location hierarchy path instead of reducing location context to the mutable leaf name
- jobs store `organisation_id` directly and keep `location_detail_text` as descriptive context only
- jobs now separate the staff actor who logged a record (`created_by`) from the resident the work belongs to (`reported_for_user_id`)
- root-level legacy placeholder locations are removed or demoted out of the active catalog during migration cleanup

## Workflow Suitability Summary

### What is supported now

- explicit intake, triage, scheduling, and execution checkpoints before completion
- blocked, on-hold, escalation, reopen, and follow-up paths
- direct contractor dispatch only when the person is anchored to a contractor organisation
- named-contractor dispatch retains contractor-organisation accountability instead of dropping back to person-only ownership
- scheduled work can remain credibly organisation-dispatched even when the exact attending technician is not yet known
- seeded demo dispatch paths now stay within two credible contractor lanes: external contractor organisations and an internal maintenance team
- contractor assigned-work queues now represent the current dispatch target only, while historically involved contractors keep read-only timeline visibility
- role-gated triage and scheduling actions
- scheduled and follow-up scheduling remain operations-owned coordination states until the contractor actually records attendance
- resident-visible timelines with structured accountability metadata
- resident-visible timelines that preserve assignment responsibility on each recorded update
- resident-visible reads that preserve the original location snapshot even if the managed location label changes later
- coordination summaries, pending signals, and visit-plan actor labels that prefer event snapshots over mutable live user and organisation rows
- resident post-visit updates can now carry a structured `charge_appeal_submitted` reason instead of forcing charge disputes into generic notes
- completed-job timelines can now surface after-hours handoff receipt, liability review, charge notice, resident appeal, and charge-resolution signals without inventing separate Phase 1 entities
- organisation-scoped resident reporting with managed location selection
- operations-scoped on-behalf intake that keeps the resident attached as the visible case owner while recording which staff path created the job
- resident visibility now follows the explicit reported-for user instead of relying on an overloaded creator field
- explicit demo-mode auth containment for seeded demo accounts and shortcut switching

### Role Semantics In The Current UI

- `resident`: submits and tracks their own reports, and remains the visible case owner even when staff log the issue on their behalf
- `reception_admin`: front desk / intake role for note-taking, clarification, and staff-created intake
- `triage_officer`: property manager role for triage and scheduling
- `coordinator`: dispatch coordinator role for assignment and operational rerouting
- `contractor`: contractor or maintenance technician role for execution updates
- `admin`: system admin role kept for bootstrap/demo/admin oversight

### Guard Conditions

| Guard | Implemented behavior |
| --- | --- |
| assignee required | `assigned`, `scheduled`, `in_progress`, `blocked`, `completed`, and `follow_up_scheduled` reject missing-assignee transitions |
| assignment clear rollback | clearing the last assignee without an explicit status change rolls the job back to `new` or `triaged` |
| assignment accountability | direct contractor dispatch keeps the contractor organisation attached alongside the named contractor |
| direct contractor credibility | direct contractor assignment rejects contractor-role users who are not members of a contractor organisation |
| triage permissions | only `triage_officer` or `admin` can move jobs to `triaged`, `scheduled`, or `follow_up_scheduled` |
| coordination permissions | only `coordinator` or `admin` can change dispatch targets |
| contractor execution scope | contractors can move work through execution states but cannot place jobs on hold from the UI |
| contractor queue truth | contractor assigned-job lists only include current dispatch targets; historical participants retain detail access without appearing in the live queue |
| accountability requirement | branch states such as `on_hold`, `blocked`, `reopened`, `follow_up_scheduled`, and `escalated` require `reason_code`; `completed` requires explicit accountability metadata |
| structured location validation | report creation requires an org-scoped, managed child `space` or `unit` location |
| historical location truth | job and event reads prefer the stored `location_snapshot` over the mutable current location row |

## Verification Evidence

- required runtime verification command: `.\.venv\Scripts\python.exe -m pytest tests\test_schema.py tests\test_migrations.py tests\test_app.py -q`
- current run execution status: pending in this sandbox until the interpreter can be executed
- latest recorded successful result in this pass: not yet available from this run
- runtime coverage in this pass includes migration bootstrap and round-trip smoke, placeholder-location cleanup, startup schema enforcement, browser login behavior, demo gating, org boundary checks, location validation, hierarchy-label rendering, historical location snapshot preservation, staff-created intake, lifecycle progression, direct contractor assignment, assignment rollback invariants, role gating, follow-up rules, note-only event creation, and role-appropriate UI controls

## Remaining Risks

- downgrade behavior is still best treated as smoke coverage rather than perfect historical rollback
- assets remain lightweight and name-driven; they are more structured than before but not yet a governed asset registry
- the current model still uses `Job` as the single operational object until the later Phase 1 split
- existing historical events created before this change still have null assignment snapshots because the repo cannot backfill that truthfully
- the model still uses `Job` as the single operational object, so dispatch, attendance, and completion evidence are recorded on one timeline rather than separate visit records

## Repository Honesty Correction

- the current repo is credible as a residence-operations coordination pilot because it keeps a shared timeline, structured location context, and org-backed dispatch accountability
- the repo is more honest after this correction because it no longer treats missing named technicians as a workflow gap when the contractor organisation and booking are already recorded
- the intake record is now more credible for that pilot because the repo can represent resident self-service, staff-mediated intake, after-hours handoff, and inspection-origin entry without pretending every job started in the same portal flow
- the job row is now more truthful because it no longer has to pretend the resident and the staff intake actor are the same person
- the current repo is not yet credible as a broader civil-works coordination platform because it still collapses intake, dispatch, attendance, and completion into one `Job`
- resident access updates now land on the coordination owner instead of being mis-stamped as triage work, which better matches the booked-attendance workflow already implemented
- the event spine now stays more truthful after completion because liability review, charge notice, resident appeal, and charge resolution can be recorded as explicit coordination signals instead of collapsing back into generic notes
- dead compatibility surface that implied a separate legacy model layer has been removed instead of being kept as misleading future-facing noise

## Deferred For Phase 1

- request -> work-order split
- structured visit/dispatch records
- richer routing-decision persistence
- public reporting, councils/homeowners, GIS/maps, and ownership verification flows
- full RBAC, invites, password reset, or enterprise auth
