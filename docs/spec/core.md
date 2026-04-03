# FixHub Core Contract — Phase 1 Event Spine

Status: active  
Scope: bounded overnight refactor  
Baseline: Phase 0.5 repo at Alembic head `20260321_0008`

## Objective

Move lifecycle state from implicit mutable job state to explicit event-backed projection, without redesigning the whole product.

This phase is intentionally narrow:
- make lifecycle transitions event-backed
- keep the current `Job` object
- preserve existing auth, demo mode, structured location flow, and current UI surfaces

## Out of scope for this phase

Do not introduce any of the following tonight:
- `request`, `work_order`, `visit`, `dispatch`, or other new top-level lifecycle tables
- UI redesigns or template rewrites
- a new RBAC system
- visibility filtering or resident/internal timeline separation
- GIS/maps/public reporting flows
- external integrations
- removal of current assignment columns from `jobs`
- auth/bootstrap/demo-mode redesign

## Canonical rules

1. `events` is the canonical history/audit record.
2. Every lifecycle change must produce exactly one event row with a non-null `target_status`.
3. `jobs.status` remains temporarily, but only as a cached projection for compatibility, filters, sorting, and existing response shapes.
4. The only authority for lifecycle state is `derive_job_status_from_events(events)`.
5. No service or route may silently change lifecycle state without emitting an event.
6. Manual note creation remains note-only. Clients must not be able to choose `event_type` or `target_status`.
7. `location_id` remains the canonical physical location reference. `location_detail_text` remains descriptive-only.
8. `Job` remains the only operational record in this phase.
9. Assignment columns may remain on `jobs` in this phase, but every assignment change must emit an `assignment` event. Assignment events are audit events, not lifecycle state, unless the workflow also emits a separate lifecycle event.
10. Alembic remains the schema authority. Do not reintroduce runtime `Base.metadata.create_all()`.

## Event contract

Add this field to `events`:

- `target_status: nullable JobStatus`

Rules:
- `target_status` is non-null for lifecycle-changing events.
- `target_status` is null for manual notes.
- `target_status` is null for pure assignment audit events.
- `report_created` must set `target_status = JobStatus.new`.
- `status_change` must set `target_status` to the moved-to status.
- `schedule` must set `target_status = JobStatus.scheduled`.
- `completion` must set `target_status = JobStatus.completed`.
- `follow_up` must set `target_status = JobStatus.follow_up_scheduled`.
- `escalation` must set `target_status = JobStatus.escalated`.

## Projection rules

Implement a pure helper:

`derive_job_status_from_events(events) -> JobStatus`

Projection behavior:
1. Order events by `(created_at, id)` ascending.
2. Ignore events where `target_status is null`.
3. The last non-null `target_status` wins.
4. If no event has a non-null `target_status`, return `JobStatus.new`.

## Cache rules

- `jobs.status` may continue to be returned by existing APIs and used in SQL filters.
- After any write path that appends events, code must recompute and persist `jobs.status` from the event stream.
- No other code may set `jobs.status` directly.
- Compatibility cache sync is allowed, but it must be derived from events, never treated as the source of truth.

## Backfill rules

The migration that adds `events.target_status` must backfill deterministic values for existing rows using only stable information already in the data.

Backfill mapping:
- `report_created` -> `new`
- `schedule` -> `scheduled`
- `completion` -> `completed`
- `follow_up` -> `follow_up_scheduled`
- `escalation` -> `escalated`
- `status_change` -> reverse-map the existing `STATUS_EVENT_MESSAGES`
- ambiguous legacy `assignment` rows -> `null`
- `note` rows -> `null`

Do not invent statuses for ambiguous historical rows.

## Current repo-specific guidance

The current repo already has:
- `app/services/workflow.py` with `append_event`, `apply_status_change`, `EventSpec`, and `STATUS_EVENT_MESSAGES`
- `app/api/jobs.py` as the main write path for report creation, assignment changes, and lifecycle updates
- `app/api/deps.py` serializing `job.status` and event payloads
- `tests/test_app.py`, `tests/test_schema.py`, and `tests/test_migrations.py` covering major behavior

Work with those structures. Do not redesign the repository.

## Acceptance criteria

A change set is acceptable only if all of the following are true:
- one new Alembic migration is added after `20260321_0008`
- `Event` and `EventRead` expose `target_status`
- a pure lifecycle projection helper exists
- report creation emits `target_status = new`
- every lifecycle transition emits a non-null `target_status`
- manual note creation still produces note-only events with `target_status = null`
- `jobs.status` stays synchronized with the derived projection
- existing auth, demo mode, structured location behavior, and current UI routes remain intact