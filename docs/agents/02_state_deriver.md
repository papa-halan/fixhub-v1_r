# Codex Prompt — 02 State Deriver

You are working in the `fixhub-v1` repository.

Read first:
- `AGENTS.md`
- `/spec/core.md`

This prompt assumes prompt `01_schema_enforcer.md` has already landed cleanly.

## Before editing

1. Run `git status --short`.
2. If any tracked file is dirty, stop and report that the worktree is not clean.
3. Do not commit.
4. Use the repo-local interpreter and tooling conventions from `AGENTS.md`.

## Current repo facts

- `jobs.status` currently exists and is used by serializers and filters.
- `app/services/workflow.py` currently contains the lifecycle logic.
- The repo does not yet have a dedicated projection helper.
- `app/api/deps.py::serialize_job()` currently reads `job.status`.
- This step must not redesign the read layer.

## Goal

Create the single lifecycle projection helper that makes events the authority and `jobs.status` a compatibility cache.

## Allowed files

You may edit only these files:
- `app/services/projections.py` (new file)
- `app/services/__init__.py`
- `tests/test_event_projection.py` (new file)

Do not edit anything else.

## Task

1. Create `app/services/projections.py`.

2. Implement a pure function:
   - `derive_job_status_from_events(events) -> JobStatus`
   - Use only `event.target_status`
   - Do not inspect `event.message` or `event.event_type`
   - Do not perform database IO
   - Do not mutate input objects

3. Projection rules must match `/spec/core.md`:
   - order events by `(created_at, id)` ascending
   - ignore events with `target_status is None`
   - last non-null `target_status` wins
   - if none exist, return `JobStatus.new`

4. Also implement a small compatibility helper in the same file:
   - `sync_job_status_from_events(job) -> JobStatus`
   - It may derive from `job.events` and assign the result into `job.status`
   - It must not commit or flush
   - Keep it narrow and reusable

5. Export the new helper(s) from `app/services/__init__.py`.

6. Add focused tests in `tests/test_event_projection.py` covering:
   - fallback to `JobStatus.new` when all `target_status` values are null
   - last non-null `target_status` wins
   - `note` events with null `target_status` do not change projection
   - deterministic ordering for same-timestamp events using `(created_at, id)`
   - `sync_job_status_from_events(job)` writes the derived value back to the job object

## Hard constraints

- Do not edit routes.
- Do not edit migrations.
- Do not edit templates or static files.
- Do not change event-writing behavior in this step.
- Do not change response models in this step.
- Keep the projection helper independent from FastAPI and SQLAlchemy session objects.

## Validation

Run:
1. `.\.venv\Scripts\python.exe -m pip install -e .`
2. `.\.venv\Scripts\python.exe -m pytest tests\test_event_projection.py -q`

## Return format

Return only:
1. files changed
2. helper names added
3. test cases added
4. validation results
5. blockers, if any