# Documentation Changelog

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
