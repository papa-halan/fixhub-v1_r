# Documentation Index

Last updated: `2026-03-21 15:27:59 +11:00`

## Document Metadata

- Owner: `student-living-platform`
- Reviewer: `schema-test-automation`
- Status: `active`

## Purpose

This folder stores implementation-aligned architecture, workflow, migration, and process notes for the current FixHub MVP.

## Structure

- [CHANGELOG.md](CHANGELOG.md): timestamped documentation history
- [architecture.md](architecture.md): implemented page/API/data architecture and accountability flow
- [chat_context_2026-03-21.md](chat_context_2026-03-21.md): handoff context for the March 2026 planning and roadmap chat
- [documentation_sop.md](documentation_sop.md): documentation update rules and freshness-gate expectations
- [known_issues.md](known_issues.md): environment and tooling caveats
- [schema_student_living_assessment.md](schema_student_living_assessment.md): current workflow assessment, guard conditions, and verification summary
- [todo_implementation_checklist.md](todo_implementation_checklist.md): remaining backlog checklist

## Current Documentation Focus

- README documents the implemented data model, lifecycle, guard conditions, and API examples
- the workflow service now owns status-transition rules, accountability guards, and event-side-effect defaults
- the schema assessment records the refined Student Living workflow now present in code
- the chat context file captures the latest strategic planning, digital-twin positioning, roadmap, and GitHub backlog work
- architecture notes show how residents, operations roles, and contractors share the same timeline
- the changelog captures what changed and how it was verified

## SD Practice Sanity Check

- Versioned history: pass
- Implemented-vs-proposed separation: pass
- Portability of links and file references: pass
- Runtime verification recorded in docs: pass
- Docs freshness gate present in test suite: pass
- Runtime execution available in current automation sandbox: blocked (`python`/`py`/`pip` unavailable; `.venv\\Scripts\\python.exe` denied in this run)

## TODO (Proposed Documentation Improvements)

- add a dedicated visit/appointment deep-dive once a first-class visit entity exists
- add CI wiring for the docs freshness gate when workflow files are introduced
