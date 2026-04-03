# Codex Prompt — 01 Schema Enforcer

You are working in the `fixhub-v1` repository.

Read first:
- `AGENTS.md`
- `/spec/core.md`

Follow repository instructions exactly.

## Before editing

1. Run `git status --short`.
2. If any tracked file is dirty, stop and report that the worktree is not clean.
3. Do not commit.
4. Use the repo-local interpreter and tooling conventions from `AGENTS.md`.

## Current repo facts

- Latest Alembic head is `20260321_0008`.
- `app/models/event.py` currently has no explicit lifecycle projection field.
- `app/schema/event.py` exposes `EventCreate` and `EventRead`.
- `tests/test_schema.py` currently asserts that `EventCreate` is note-only.
- `tests/test_migrations.py` currently asserts there is a single head.

## Goal

Add the minimum schema support required for Phase 1 event-backed lifecycle projection.

## Allowed files

You may edit only these files:
- `app/models/event.py`
- `app/schema/event.py`
- `app/schema/__init__.py` only if strictly required
- `alembic/versions/<new_migration>.py`
- `tests/test_schema.py`
- `tests/test_migrations.py`

Do not edit anything else.

## Task

1. Add nullable `target_status` to `Event` in `app/models/event.py`.
   - Use the existing `JobStatus` enum.
   - Keep it nullable.
   - Do not remove or rename any current event columns.

2. Add `target_status: JobStatus | None = None` to `EventRead` in `app/schema/event.py`.
   - Do not change `EventCreate`.
   - `EventCreate` must remain note-only.

3. Add one new Alembic migration after `20260321_0008`.
   - Keep naming consistent with existing migrations.
   - The migration must:
     - add `events.target_status`
     - backfill deterministic historical values
     - leave `jobs.status` untouched

4. Backfill rules must match `/spec/core.md`.
   - Prefer explicit event-type mapping first.
   - For `status_change`, reverse-map the current workflow messages.
   - For ambiguous rows, leave `target_status` null.
   - Do not import app services inside the migration. Keep the mapping local to the migration file.

5. Update migration tests as needed.
   - The repo must still have exactly one head.
   - The new head must be the new migration revision.

6. Update schema tests as needed.
   - Preserve the assertion that `EventCreate` rejects extra fields such as `event_type`.

## Hard constraints

- No new tables.
- No triggers.
- No docs changes.
- No API route changes.
- No workflow/service changes in this step.
- Do not touch `app/models/job.py`.
- Do not touch `app/api/jobs.py`.
- Do not touch `app/services/workflow.py`.

## Validation

Run, in this order if needed:
1. `.\.venv\Scripts\python.exe -m pip install -e .`
2. `.\.venv\Scripts\python.exe -m pytest tests\test_schema.py tests\test_migrations.py -q`

## Return format

Return only:
1. files changed
2. migration revision id and filename
3. brief backfill summary
4. validation results
5. blockers, if any