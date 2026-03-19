# Documentation Index

Last updated: `2026-03-19 15:04:12 +11:00`

## Document Metadata

- Owner: `student-living-platform`
- Reviewer: `schema-test-automation`
- Status: `active`

## Purpose

This folder stores implementation-aligned architecture, workflow, migration, and process notes for the current FixHub MVP.

## Structure

- [CHANGELOG.md](CHANGELOG.md): timestamped documentation history
- [architecture.md](architecture.md): implemented page/API/data architecture and accountability flow
- [documentation_sop.md](documentation_sop.md): documentation update rules and freshness-gate expectations
- [known_issues.md](known_issues.md): environment and tooling caveats
- [schema_student_living_assessment.md](schema_student_living_assessment.md): current workflow assessment, guard conditions, and verification summary
- [todo_implementation_checklist.md](todo_implementation_checklist.md): remaining backlog checklist

## Current Documentation Focus

- README documents the implemented data model, lifecycle, guard conditions, and API examples
- the schema assessment records the refined Student Living workflow now present in code
- architecture notes show how residents, operations roles, and contractors share the same timeline
- the changelog captures what changed and how it was verified

## SD Practice Sanity Check

- Versioned history: pass
- Implemented-vs-proposed separation: pass
- Portability of links and file references: pass
- Runtime verification recorded in docs: pass
- Docs freshness gate present in test suite: pass
- Runtime execution available in current automation sandbox: blocked (static evidence only)

## TODO (Proposed Documentation Improvements)

- add a dedicated visit/appointment deep-dive once a first-class visit entity exists
- add CI wiring for the docs freshness gate when workflow files are introduced
