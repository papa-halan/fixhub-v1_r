# Documentation SOP

Last updated: `2026-03-19 14:35:04 +11:00`

## Document Metadata

- Owner: `student-living-platform`
- Reviewer: `schema-test-automation`
- Status: `draft`

## Mandatory Update Triggers

Update documentation in the same change set when any of the following change:

- SQLAlchemy model fields, enums, or relationships.
- API request/response schemas under `app/schema`.
- route surfaces or route-level behavior under `app/api`.
- lifecycle or permission rules (`app/api/deps.py`).
- user-visible status/timeline behavior in templates.

## Required Documentation Touchpoints

- `README.md`: diagrams only for architecture/schema/lifecycle deltas.
- `docs/schema_student_living_assessment.md`: implemented baseline and run log updates.
- `docs/CHANGELOG.md`: timestamped documentation/code change note.
- `docs/todo_implementation_checklist.md`: update completed/pending TODO checkboxes.

## Changelog Pattern

For each run, append a version entry with:

- version tag and timestamp,
- `Added` and/or `Changed` bullets,
- verification status (`runtime verified` or `static-only` with blocker reason).

## Verification Recording Rule

- Preferred: include command and pass/fail summary (`python -m pytest ...`).
- If blocked: record exact blocker message and mark run as static/code-evidence only.

## Docs Freshness Gate

- Local quality gate: `tests/test_docs_freshness.py` runs with the normal `python -m pytest` suite.
- Rule: if tracked code surfaces (`app/models`, `app/api`, `app/schema`, `app/services`, `alembic/versions`) are newer than required docs, the gate fails.
- Required docs for freshness: `README.md`, `docs/README.md`, `docs/CHANGELOG.md`, and `docs/schema_student_living_assessment.md`.

## Intentional Exception Override

- Set `FIXHUB_DOCS_FRESHNESS_BYPASS=1` to bypass the docs freshness gate for emergency/hotfix scenarios.
- Any bypass must still be recorded in `docs/CHANGELOG.md` notes for auditability.
