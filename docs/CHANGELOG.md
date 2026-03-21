# Documentation Changelog

## Document Metadata

- Owner: `student-living-platform`
- Reviewer: `schema-test-automation`
- Status: `active`

## [0.5.0] - 2026-03-21 16:20:58 +11:00

### Changed
- refreshed `README.md` to document the Phase 0 stabilization outcome: migrations-first boot, signed-cookie session auth, explicit demo mode, and resident report creation via structured `location_id`.
- refreshed `docs/README.md` to reflect the current verification status and the new org/location/auth foundation.
- refreshed `docs/schema_student_living_assessment.md` with the stabilized workflow summary, Phase 0.5 schema notes, and latest executable verification result.

### Notes
- runtime verification succeeded in this environment with `.\.venv\Scripts\python.exe -m pytest -q`.
- result: `27 passed`.
- this run intentionally stops before the larger Phase 1 request/work-order/visit split.

## [0.4.5] - 2026-03-21 15:27:59 +11:00

### Added
- `docs/chat_context_2026-03-21.md` with a full new-chat handoff covering repo exploration, specialist review findings, AMS/CMS/CMMS and digital-twin positioning, the finalized phased implementation plan, the quarter-by-quarter roadmap, and the GitHub issue backlog produced in the planning chat.

### Changed
- updated `docs/README.md` to index the new chat-context handoff file and reflect the latest documentation timestamp.

### Notes
- this run is documentation-only; no application code was changed.
- the new handoff doc is intended to let a fresh chat continue with implementation planning or execution without replaying the entire prior conversation.

## [0.4.4] - 2026-03-19 16:03:23 +11:00

### Changed
- reviewed commit evidence since automation last run (`2026-03-19T04:09:45.240Z`): `0668f89ad113dba36ecf399066f08d8c5defc14f` and `b98e309fd74a5edf074606b33d4961799decefb7`.
- validated that post-run changes include workflow-service extraction, accountability guard updates, and expanded lifecycle/edge-case tests by inspecting diffs and current repository state.
- refreshed `docs/README.md`, `docs/schema_student_living_assessment.md`, and `docs/todo_implementation_checklist.md` with this run's timestamped evidence and status.

### Notes
- required runtime commands were attempted but blocked in this sandbox (`python`/`py`/`pip` unavailable; `.venv\\Scripts\\python.exe` execution denied), so this run is grounded on git/test-code evidence only.
- no additional code fix was applied because commit diffs did not present a new concrete regression requiring a minimal patch.

## [0.4.3] - 2026-03-19 15:24:12 +11:00

### Changed
- extracted workflow/state-machine helpers into `app/services/workflow.py` so transition rules, accountability defaults, and event side effects are owned by the service layer rather than `app/api/deps.py`
- tightened completion accountability: moving a job to `completed` now requires an explicit `reason_code` or `responsibility_stage`
- updated operations and contractor job pages so reason-coded transitions can be supplied from the UI, and contractor completion sends `responsibility_stage=execution`
- expanded `tests/test_app.py` coverage for blocked, on-hold, reopened, and explicit completion-accountability paths
- refreshed `README.md`, `docs/README.md`, `docs/schema_student_living_assessment.md`, and `docs/todo_implementation_checklist.md` to match the verified runtime behavior

### Notes
- runtime verification succeeded in this environment with `.\.venv\Scripts\python.exe -m pytest tests\test_schema.py tests\test_app.py` and `.\.venv\Scripts\python.exe -m ruff check app tests`
- result: `23 passed`, `ruff` clean
- this workspace already contained dirty-worktree documentation entries timestamped later than the current environment clock; this entry records the actual runtime timestamp from the current session

## [0.4.2] - 2026-03-19 15:12:17 +11:00

### Changed
- performed schema-test automation evidence scan for commits since `2026-03-19T04:00:56.070Z`; reviewed `9c0a0b5397318d6d2a97774ade77e73de0ed0482` and `f7877bd00ca0e4837f82db0364d73bcde83310ab`.
- verified resident->operations->contractor lifecycle and edge-case coverage against existing tests (`tests/test_app.py`, `tests/test_schema.py`) using static repository inspection.
- refreshed backlog status notes in `docs/todo_implementation_checklist.md` for remaining product-track TODOs and current validation blocker.

### Notes
- no additional code fix was applied in this run because no new concrete regression was identified from commit diff evidence alone.
- required runtime commands remain blocked in this sandbox (`python`/`py` unavailable; `.venv\\Scripts\\python.exe` execution denied), so this run is static/code-evidence verified only.

## [0.4.1] - 2026-03-19 15:04:12 +11:00

### Changed
- corrected assignment-permission API detail text in `app/api/jobs.py` to match implemented role logic (`admin` and `coordinator` can assign).

### Notes
- commit scan since last run (`2026-03-19T03:31:31.650Z`) found no new commits.
- latest commit in the 24h scan window remains `dcef84a5c27b2f611e9f0ccfca4777109e4c7d87` (`2026-03-19 13:51:04 +11:00`).
- runtime command execution remains blocked (`python`/`py` unavailable; `.venv\\Scripts\\python.exe` access denied), so this run is static/code-evidence verified.

## [0.4.0] - 2026-03-19 17:20:00 +11:00

### Added
- documentation for direct contractor dispatch via `assigned_contractor_user_id`
- documentation for structured event metadata: `event_type`, `responsibility_stage`, and `owner_scope`
- documentation for Student Living operations sub-roles and organisation hierarchy
- Alembic migration note for `20260319_0005_operational_workflow_refactor.py`

### Changed
- refreshed `README.md` with updated ER diagram, simplified business state diagram, guard-condition table, and API examples
- refreshed `docs/README.md`, `docs/architecture.md`, and `docs/schema_student_living_assessment.md` to reflect the refined lifecycle and assignment semantics

### Notes
- runtime verification succeeded in this environment with `python -m pytest tests\test_schema.py tests\test_app.py`
- result: `20 passed`

## [0.3.9] - 2026-03-19 14:35:04 +11:00

### Added
- local docs freshness quality gate test: `tests/test_docs_freshness.py`.

### Changed
- updated `docs/documentation_sop.md` with docs freshness gate rules and intentional bypass instructions.
- updated `docs/README.md` to reflect local docs freshness enforcement status and remaining CI TODO.
- updated `docs/todo_implementation_checklist.md` to mark B4 docs freshness gate tasks complete.

### Notes
- commit scan since last run (`2026-03-19T03:24:08.646Z`) found no new commits.
- latest commit in the 24h scan window remains `dcef84a5c27b2f611e9f0ccfca4777109e4c7d87`.
- runtime command execution remains blocked (`python`/`py` unavailable; `.venv\\Scripts\\python.exe` access denied), so this run is static/code-evidence verified.

## [0.3.8] - 2026-03-19 14:26:43 +11:00

### Added
- `docs/architecture.md` with Mermaid architecture flow for current pages, routes, entities, and event flow.
- `docs/documentation_sop.md` defining mandatory doc update triggers and changelog/verification recording rules.
- `docs/known_issues.md` documenting current Python runtime execution blockers and mitigation paths.

### Changed
- updated `README.md` diagrams (ER, flow, state machine) to match implemented branch lifecycle and event metadata fields.
- updated `docs/schema_student_living_assessment.md` baseline to reflect implemented branch statuses and event handoff fields.
- updated `docs/todo_implementation_checklist.md` to mark completed A1 and documentation-track items implemented in repository docs.
- updated `docs/README.md` to add metadata convention and links for newly added documentation files.
- updated `.gitignore` to include `.pytest-tmp-codex/` and keep transient test artifacts out of tracked commits.

### Notes
- commit scan since last run found no new commits after `2026-03-19T03:00:55.139Z`; latest recent commit reviewed: `dcef84a5c27b2f611e9f0ccfca4777109e4c7d87`.
- runtime command execution remained blocked in this environment (`python`/`py` unavailable; `.venv\\Scripts\\python.exe` denied execution), so this run is static/code-evidence verified.

## [0.3.7] - 2026-03-19 14:13:16 +11:00

### Added
- branch-state lifecycle support in code: `on_hold`, `blocked`, `cancelled`, `reopened`.
- structured transition metadata fields in events: `reason_code` and `responsibility_owner`.
- Alembic migration `20260319_0003_branch_status_and_handoff_metadata.py` for status/metadata rollout.

### Changed
- guarded status transition logic now requires `reason_code` and `responsibility_owner` for branch transitions.
- API schema/serialization now surfaces transition metadata for timeline/event consumers.
- timeline UI now shows reason and owner when branch-state metadata is present.
- updated schema/app tests to validate guarded transition behavior and new enum/field surfaces.

### Notes
- runtime verification succeeded in this environment: `45 passed` across `tests/test_schema.py` and `tests/test_app.py`.

## [0.3.6] - 2026-03-19 13:56:41 +11:00

### Changed
- updated `README.md` Mermaid diagrams only (architecture and state machine) to reflect current implemented route flow and lifecycle behavior.
- refreshed `docs/README.md` timestamp, structure wording, SD-practice sanity checks, and documentation-process feedback.
- refreshed `docs/schema_student_living_assessment.md` top date/runtime verification status and appended a timestamped `refactor-docs-and-readme-md` run log.
- refreshed `docs/todo_implementation_checklist.md` timestamp and marked documentation-sync checklist items completed for this run.

### Notes
- this run is documentation-only and remains aligned to currently implemented code/schema behavior.
- runtime test execution remains blocked in this environment (`python` unavailable and `.venv\\Scripts\\python.exe` launch denied).

## [0.3.5] - 2026-03-15 18:31:34 +11:00

### Added
- documentation for persistent `locations` and `assets` catalog support in the schema/workflow assessment.

### Changed
- updated `README.md` scope, ER diagram, flow diagram, architecture diagram, and notes to reflect the location/asset catalog.
- refreshed `docs/README.md` timestamp and diagram coverage note for the expanded schema.
- refreshed `docs/schema_student_living_assessment.md` baseline and validation evidence to reflect six tables and 28 passing schema/app tests.

### Notes
- current codebase now persists resident-reported location/asset context across jobs and events.

## [0.3.4] - 2026-03-15 18:16:11 +11:00

### Added
- current-state documentation of the dedicated `app/schema` package and its role in the API contract.
- manual schema-doc sync run log in `docs/schema_student_living_assessment.md` with passing runtime verification evidence.

### Changed
- updated `README.md` to document `app/models` vs `app/schema` responsibilities and include the schema layer in the architecture diagram.
- refreshed `docs/README.md` verification status to reflect green schema/app pytest coverage in this environment.
- refreshed `docs/schema_student_living_assessment.md` scope, baseline notes, and validation evidence to match the current codebase.

### Notes
- current codebase separates persistence models (`app/models`) from API schemas (`app/schema`).
- runtime verification succeeded for the synced schema/app suite (`24 passed` across `tests/test_schema.py` and `tests/test_app.py`).

## [0.3.3] - 2026-03-15 17:30:56 +11:00

### Added
- Mermaid `Architecture Diagram` added to `README.md` diagrams section.

### Changed
- refreshed `README.md` diagrams section to include full current implementation visuals (ER, flow chart, architecture diagram, state machine).
- updated `docs/README.md` timestamp and SD-practice checks to include diagram coverage status.
- refreshed `docs/todo_implementation_checklist.md` run timestamp and release validation note.
- appended `2026-03-15` run log in `docs/schema_student_living_assessment.md` for documentation-sync traceability.

### Notes
- no new app/schema code changes were introduced in this run; updates are documentation-only and aligned to existing code/tests.
- runtime pytest execution remains blocked in this environment by Python startup error (`ModuleNotFoundError: No module named 'encodings'`).

## [0.3.2] - 2026-03-14 00:02:29 +11:00

### Added
- new schema-test run log section in `docs/schema_student_living_assessment.md` covering UoN Student Living edge cases, JLC gaps, and prioritized refactor recommendations.
- targeted schema/workflow edge-case tests in `tests/test_app.py` for assignment type validation, lifecycle transition guards, assignment rollback behavior, and independent-contractor access limits.

### Notes
- runtime pytest execution remains blocked in this environment by Python startup error (`ModuleNotFoundError: No module named 'encodings'`).

## [0.3.1] - 2026-03-13 23:28:11 +11:00

### Added
- `docs/todo_implementation_checklist.md` with executable checkbox checklist for all current proposed TODOs.

### Changed
- updated `docs/README.md` structure index to include the TODO implementation checklist.

## [0.3.0] - 2026-03-13 23:17:31 +11:00

### Added
- `docs/README.md` to define docs structure, standards, SD sanity checks, and process feedback.
- explicit documentation TODO backlog sections for proposed improvements.

### Changed
- updated `README.md` with implemented development changes, docs links, and documentation TODOs.
- refactored `docs/schema_student_living_assessment.md` to use portable links and explicit implemented-vs-proposed separation.

### Notes
- this run records only already-implemented code changes observed in repository diffs.

## [0.2.0] - 2026-03-13 15:43:19 +11:00

### Historical Note
- previous run reported docs metadata/changelog/ADR additions; current workspace state did not include those files.

## [0.1.0] - 2026-03-13 15:21:56 +11:00

### Historical Note
- previous run reported initial full docs refactor for README and docs markdown files.
