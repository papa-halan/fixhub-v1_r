# Documentation Index

Last updated: `2026-03-21 16:20:58 +11:00`

## Document Metadata

- Owner: `student-living-platform`
- Reviewer: `schema-test-automation`
- Status: `active`

## Purpose

This folder stores implementation-aligned architecture, workflow, migration, auth, and process notes for the current FixHub MVP.

## Structure

- [CHANGELOG.md](CHANGELOG.md): timestamped documentation history
- [architecture.md](architecture.md): implemented page/API/data architecture and accountability flow
- [chat_context_2026-03-21.md](chat_context_2026-03-21.md): handoff context for the March 2026 planning and roadmap chat
- [documentation_sop.md](documentation_sop.md): documentation update rules and freshness-gate expectations
- [known_issues.md](known_issues.md): environment and tooling caveats
- [schema_student_living_assessment.md](schema_student_living_assessment.md): current workflow assessment, guard conditions, and verification summary
- [todo_implementation_checklist.md](todo_implementation_checklist.md): remaining backlog checklist

## Current Documentation Focus

- README documents the migrations-first boot flow, signed-session auth, org-scoped locations, lifecycle guards, and API examples
- the workflow service owns status-transition rules, accountability guards, and event-side-effect defaults
- the schema assessment records the stabilized Student Living workflow plus the Phase 0.5 organisation/location foundation now present in code
- the chat context file captures the latest strategic planning, digital-twin positioning, roadmap, and GitHub backlog work
- architecture notes show how residents, operations roles, and contractors share the same timeline
- the changelog captures what changed and how it was verified

## SD Practice Sanity Check

- Versioned history: pass
- Implemented-vs-proposed separation: pass
- Portability of links and file references: pass
- Runtime verification recorded in docs: pass
- Docs freshness gate present in test suite: pass
- Runtime execution available in current environment: pass

## TODO (Proposed Documentation Improvements)

- add a dedicated visit/appointment deep-dive once a first-class visit entity exists
- add CI wiring for the docs freshness gate when workflow files are introduced
