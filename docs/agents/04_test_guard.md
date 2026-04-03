# Codex Prompt — 04 Test Guard

You are working in the `fixhub-v1` repository.

Read first:
- `AGENTS.md`
- `/spec/core.md`

This prompt assumes prompts `01_schema_enforcer.md`, `02_state_deriver.md`, and `03_event_builder.md` have already landed cleanly.

## Before editing

1. Run `git status --short`.
2. If any tracked file is dirty, stop and report that the worktree is not clean.
3. Do not commit.
4. Use the repo-local interpreter and tooling conventions from `AGENTS.md`.

## Goal

Add regression coverage that proves the event spine is real, the compatibility cache is synchronized, and the migration/backfill behavior is stable.

## Allowed files

You may edit only these files:
- `tests/test_event_projection.py`
- `tests/test_app.py`
- `tests/test_schema.py`
- `tests/test_migrations.py`
- `tests/support.py` only if a tiny helper is strictly required

Do not edit anything else.

## Task

Add or update tests so the suite proves all of the following:

1. Schema and API shape
   - `EventRead` includes `target_status`
   - `EventCreate` remains note-only and still rejects forged extra lifecycle fields

2. Projection behavior
   - the last non-null `target_status` wins
   - note events with null `target_status` do not change derived state
   - cache sync helper writes the derived status into `job.status`

3. Write-path behavior
   - report creation produces an initial event with `target_status="new"`
   - moving a job through normal lifecycle transitions produces events with explicit `target_status`
   - manual note endpoint produces `target_status=null`
   - assignment from `new` emits both assignment audit and lifecycle state in a way that keeps the cache correct
   - assignment clearing fallback emits an explicit lifecycle event and the final cached status matches projection

4. Migration/backfill behavior
   - the new migration backfills `target_status` for deterministic legacy lifecycle rows
   - ambiguous historical note or assignment rows remain null
   - there is still exactly one Alembic head

5. Compatibility
   - existing demo/auth/location flows are not broken by the new field
   - existing tests that previously asserted lifecycle flows continue to pass

## Guidance

- Prefer extending current tests rather than rewriting them.
- Keep assertions focused on observable behavior.
- If a validation failure reveals a problem outside allowed files, stop and report it instead of widening scope.

## Validation

Run:
1. `.\.venv\Scripts\python.exe -m pip install -e .`
2. `.\.venv\Scripts\python.exe -m pytest -q`

## Return format

Return only:
1. files changed
2. new/updated test names
3. full validation result summary
4. blockers, if any