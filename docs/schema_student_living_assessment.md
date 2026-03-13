# Schema Test: UoN Student Living Resident Reporting

Date: `2026-03-13 23:17:31 +11:00`
Scope: code-level schema and workflow validation in [app/models/mvp.py](../app/models/mvp.py), [app/models/enums.py](../app/models/enums.py), [app/main.py](../app/main.py), [app/services/demo.py](../app/services/demo.py), and [tests/test_app.py](../tests/test_app.py).

## Implemented Baseline (Current State)

- Core entities remain: `organisations`, `users`, `jobs`, `events`.
- User roles remain: `resident`, `admin`, `contractor`.
- Organisation types remain: `university`, `contractor`.
- Job statuses remain: `new`, `assigned`, `in_progress`, `completed`.
- Effective lifecycle remains linear dispatch with event timeline evidence.

## Implemented Changes Observed In This Run

- `DATABASE_URL` default in [app/core/config.py](../app/core/config.py) now targets PostgreSQL instead of SQLite.
- `docker-compose.yml` now sets `FIXHUB_DEFAULT_USER` for startup user context.
- UI forms now declare `method="post"` in:
- [app/templates/resident_report.html](../app/templates/resident_report.html)
- [app/templates/admin_job.html](../app/templates/admin_job.html)
- [app/templates/contractor_job.html](../app/templates/contractor_job.html)
- base template script loading changed in [app/templates/base.html](../app/templates/base.html) to non-deferred script include.
- coverage added in [tests/test_app.py](../tests/test_app.py): `test_report_page_wires_post_form`.

## Validation Evidence

- Structural evidence: schema footprint in tests still asserts exactly four tables (`events`, `jobs`, `organisations`, `users`).
- Workflow evidence: resident-admin-contractor flow still validates assignment, event creation, and status progression.
- Runtime execution in this environment: full pytest execution remains blocked by Python startup error (`ModuleNotFoundError: No module named 'encodings'`) as previously observed; code-level assertions were used as evidence.

## Resident-Centric Suitability Summary

- Intake creation and timeline visibility: pass.
- Assignment visibility and contractor updates: pass.
- Multi-trade dispatch, blocked states, reopen/escalation semantics: not implemented in current schema.
- Fine-grained Student Living role boundaries: not implemented in current role model.

## SD Documentation Practice Sanity Check

- Facts vs proposals separation: pass (this document now separates implemented and TODO).
- Source traceability to code/tests: pass (all current-state claims mapped to repository files).
- Portability for sharing: pass (repository-relative links; no machine-specific paths).
- Verification depth: partial (runtime test execution not available in this environment).

## Feedback On Documentation Process (Against Standard SD Practice)

- Positive: implemented-state logging is now explicit and timestamped, reducing ambiguity.
- Positive: docs now include a dedicated changelog and index, improving discoverability.
- Gap: runtime verification evidence should be attached per run once environment issues are fixed.
- Gap: historical docs continuity relied on memory; persisted files were missing and had to be reconstructed.

## TODO (Proposed Product Improvements)

- add explicit blocked/on-hold/reopen/escalation lifecycle states.
- split resident request from execution work order for 1:N dispatch.
- model Student Living operational roles (reception/triage/coordinator) explicitly.
- add structured appointment/visit entities and reason-coded routing decisions.

## TODO (Proposed Documentation Improvements)

- add a repeatable schema test checklist section with expected commands and output snippets.
- add a dedicated "Known environment issues" doc for Python/runtime setup constraints.
- include an owner/reviewer metadata block per major document once team ownership is defined.
