# Documentation Changelog

## Document Metadata

- Owner: `student-living-platform`
- Reviewer: `schema-test-automation`
- Status: `active`

## [0.6.3] - 2026-03-22 17:40:31 +11:00

### Added
- added `docs/uon_student_living_maintenance_context.md` as an append-only research log for the University of Newcastle Student Living maintenance workflow

### Changed
- updated `docs/README.md` to index the new UoN maintenance-context research log and reflect the latest documentation timestamp

### Notes
- this run is documentation and research only; no application code was changed
- external evidence came from current UoN Student Living 2026 resource pages, guides, and terms

## [0.6.2] - 2026-03-22 17:15:11 +11:00

### Changed
- documented the seeded demo login roster and shared demo password in `README.md`
- documented that normal mode can explicitly seed the demo users for full-suite verification while keeping demo shortcuts and `/switch-user` disabled
- aligned auth/session behavior so seeded demo accounts can sign in anywhere they are intentionally created, instead of being rejected outside demo mode

### Notes
- verification reached `.\.venv\Scripts\python.exe -m pytest` with one docs-freshness follow-up still pending at the time of this changelog entry
- targeted auth regression coverage passed for bootstrap-only normal mode, unseeded normal mode, and normal mode with seeded demo users

## [0.6.1] - 2026-03-21 18:31:16 +11:00

### Changed
- removed the accidental Phase 1 request/work-order/visit/routing documentation drift from README and assessment docs
- documented the corrected Phase 0.5 scope: structured org-scoped locations, current job/event lifecycle, and deferred Phase 1 split
- documented the browser form login flow, explicit demo-mode gating, and the new optional bootstrap-user path for normal-mode startup
- refreshed role language to distinguish system admin, front desk, property manager, dispatch coordinator, and contractor/maintenance actors
- refreshed `docs/README.md`, `docs/schema_student_living_assessment.md`, and `docs/todo_implementation_checklist.md` to match the corrected runtime behavior

### Notes
- verification succeeded for the full suite with `.\.venv\Scripts\python.exe -m pytest -q`
- result: `33 passed`

## [0.5.0] - 2026-03-21 16:20:58 +11:00

### Changed
- refreshed `README.md` to document the Phase 0 stabilization outcome: migrations-first boot, signed-cookie session auth, explicit demo mode, and resident report creation via structured `location_id`
- refreshed `docs/README.md` to reflect the current verification status and the new org/location/auth foundation
- refreshed `docs/schema_student_living_assessment.md` with the stabilized workflow summary, Phase 0.5 schema notes, and latest executable verification result

### Notes
- runtime verification succeeded in this environment with `.\.venv\Scripts\python.exe -m pytest -q`
- result: `27 passed`
- this run intentionally stopped before the larger Phase 1 request/work-order/visit split

## [0.4.5] - 2026-03-21 15:27:59 +11:00

### Added
- `docs/chat_context_2026-03-21.md` with a full new-chat handoff covering repo exploration, specialist review findings, AMS/CMS/CMMS and digital-twin positioning, the finalized phased implementation plan, the quarter-by-quarter roadmap, and the GitHub issue backlog produced in the planning chat

### Changed
- updated `docs/README.md` to index the new chat-context handoff file and reflect the latest documentation timestamp

### Notes
- this run is documentation-only; no application code was changed
- the new handoff doc is intended to let a fresh chat continue with implementation planning or execution without replaying the entire prior conversation
# Changelog

## 2026-04-04

- stopped creating new `assets` from resident free-text report intake
- made asset selection optional and restricted asset linkage to known location assets
- updated README workflow language to reflect optional asset capture instead of implied structured certainty
