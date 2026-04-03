# Codex Prompt — 03 Event Builder

You are working in the `fixhub-v1` repository.

Read first:
- `AGENTS.md`
- `/spec/core.md`

This prompt assumes prompts `01_schema_enforcer.md` and `02_state_deriver.md` have already landed cleanly.

## Before editing

1. Run `git status --short`.
2. If any tracked file is dirty, stop and report that the worktree is not clean.
3. Do not commit.
4. Use the repo-local interpreter and tooling conventions from `AGENTS.md`.

## Current repo facts

- `app/services/workflow.py` currently defines `EventSpec`, `append_event`, `apply_status_change`, and status transition rules.
- `apply_status_change()` currently mutates `job.status` directly.
- `build_assignment_events()` currently performs implicit status changes during assignment flows.
- `app/api/jobs.py` is the main write path for report creation, patch updates, and manual note creation.
- `app/api/deps.py::serialize_event()` currently does not expose `target_status`.

## Goal

Wire the existing write paths so lifecycle state is recorded as explicit event data and the `jobs.status` cache is synchronized from the event stream.

## Allowed files

You may edit only these files:
- `app/services/workflow.py`
- `app/services/__init__.py`
- `app/api/jobs.py`
- `app/api/deps.py`
- `tests/test_app.py` only if a narrow assertion update is required

Do not edit anything else.

## Task

1. Extend `EventSpec` with:
   - `target_status: JobStatus | None = None`

2. Extend `append_event()` so it can accept:
   - `target_status: JobStatus | None = None`

3. Make `append_event()` the single place that keeps the compatibility cache synchronized.
   - After creating the event, recompute job status from the event stream using the helper from `app/services/projections.py`
   - Keep the existing `updated_at` touch behavior
   - Do not commit inside the helper

4. Ensure the new event is attached to the in-memory job relationship before projection sync.
   - Either associate the event through the relationship or otherwise guarantee that derivation sees the newly added event before commit
   - Choose the smallest safe approach

5. Refactor lifecycle write paths so they no longer treat direct `job.status` mutation as the source of truth.
   - In `apply_status_change()`, stop using `job.status = target` as the primary recording mechanism
   - Return an `EventSpec` with `target_status=target`
   - Preserve all existing permission checks and transition validation

6. Refactor assignment side effects.
   - In `build_assignment_events()`, any implicit lifecycle movement such as `assigned` or fallback rollback must be represented by an explicit status event spec with a non-null `target_status`
   - Pure assignment audit events must keep `target_status=None`

7. Ensure report creation emits:
   - `report_created` event with `target_status=JobStatus.new`

8. Ensure manual note creation remains note-only.
   - `/api/jobs/{job_id}/events` must still create note events only
   - manual notes must set `target_status=None`
   - residents must still be blocked from adding events

9. Update `serialize_event()` in `app/api/deps.py` to expose `target_status` in API responses.
   - Use the enum value string when present
   - Return `None` when absent

## Hard constraints

- Do not redesign routes.
- Do not add new endpoints.
- Do not change templates or static files.
- Do not remove `jobs.status`.
- Do not remove assignment columns from `jobs`.
- Do not weaken current permission checks.
- Do not change the current response shape for jobs except through the existing cached `status`.

## Validation

Run:
1. `.\.venv\Scripts\python.exe -m pip install -e .`
2. `.\.venv\Scripts\python.exe -m pytest tests\test_app.py -q`

## Return format

Return only:
1. files changed
2. summary of write-path changes
3. where `target_status` is now emitted
4. validation results
5. blockers, if any