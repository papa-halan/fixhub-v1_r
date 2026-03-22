# Documentation Index

Last updated: `2026-03-22 17:40:31 +11:00`

## Document Metadata

- Owner: `student-living-platform`
- Reviewer: `schema-test-automation`
- Status: `active`

## Purpose

This folder stores implementation-aligned notes for the current FixHub MVP.

## Structure

- [CHANGELOG.md](CHANGELOG.md): timestamped documentation history
- [architecture.md](architecture.md): implemented page/API/data architecture
- [chat_context_2026-03-21.md](chat_context_2026-03-21.md): handoff context for the March 2026 planning and roadmap chat
- [documentation_sop.md](documentation_sop.md): documentation update rules and freshness-gate expectations
- [known_issues.md](known_issues.md): environment and tooling caveats
- [uon_student_living_maintenance_context.md](uon_student_living_maintenance_context.md): append-only research log mapping the real UoN Student Living maintenance process onto FixHub's workflow model
- [schema_student_living_assessment.md](schema_student_living_assessment.md): current workflow assessment and verification summary
- [todo_implementation_checklist.md](todo_implementation_checklist.md): remaining backlog checklist

## Current Documentation Focus

- README documents the migrations-first boot flow, signed-session auth, explicit demo vs normal startup, the seeded demo login roster, and the current org/location/job/event model
- the schema assessment records the corrected Phase 0.5 foundation: structured locations, same-org validation, real login in normal mode, explicit demo gating, and current workflow guards
- the handoff context file captures the latest strategic planning, digital-twin positioning, roadmap, and GitHub backlog work
- the UoN Student Living maintenance context log captures current real-world actor and workflow evidence so future FixHub modeling stays grounded in the university's actual operating process
- architecture notes show how residents, operations roles, and contractors share the same timeline
- the changelog records what changed and how it was verified

## Current Scope Boundary

- implemented now: stabilization plus Phase 0.5 foundation
- deferred: request -> work-order -> visit split, richer routing records, public reporting, enterprise auth, and broader CMMS features

## SD Practice Sanity Check

- Versioned history: pass
- Implemented-vs-proposed separation: pass
- Portability of links and file references: pass
- Runtime verification recorded in docs: pass
- Docs freshness gate present in test suite: pass
- Demo-vs-normal startup distinction documented: pass
