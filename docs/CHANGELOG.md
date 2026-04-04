# Documentation Changelog

## Document Metadata

- Owner: `fixhub-pilot`
- Reviewer: `schema-test-automation`
- Status: `active`

## [0.6.16] - 2026-04-04 22:42:00 +11:00

### Changed
- operations can now create a job on behalf of a resident through a structured intake channel instead of forcing every report to look like direct resident self-service
- `report_created` events now carry intake provenance that distinguishes resident portal, staff-created, after-hours, and inspection / housekeeping entry paths
- queue and detail views now show who logged the job and how it entered the workflow, so staff, residents, and contractors can read a truer intake record

### Notes
- this run improved pilot intake realism and reduced a misleading demo-era assumption without widening the current job/event model

## [0.6.14] - 2026-04-04 21:18:00 +11:00

### Changed
- resident updates now require an explicit structured reason code instead of allowing ambiguous free-form "general" notes
- post-visit resident signals are constrained to plausible lifecycle states, so confirmation and recurrence cannot be recorded before a completion/follow-up path exists
- the resident job page now only offers update types that match the current lifecycle state

### Notes
- this run tightened pilot truth around resident-to-operations coordination without widening the current job/event model

## [0.6.16] - 2026-04-04 22:30:00 +11:00

### Changed
- job-level assignment projection now prefers the latest assignment-event name snapshots over live organisation/user rows, so current dispatch labels stay aligned with the recorded handoff after later renames
- added regression coverage for resident and operations reads when contractor organisation or named field-worker rows are renamed after assignment

### Notes
- this run corrected a timeline-truth gap in the existing event-backed dispatch model instead of adding new workflow surface

## [0.6.15] - 2026-04-04 22:05:00 +11:00

### Changed
- `scheduled` and `follow_up_scheduled` lifecycle events now default to `responsibility_owner=triage_officer` instead of `contractor`, so pre-attendance work stays stamped as operations-owned coordination
- added regression coverage to keep pre-attendance ownership aligned with the event model and resident-facing workflow
- updated architecture and schema assessment docs to describe contractor ownership beginning at recorded attendance rather than booking

### Notes
- this run removed a misleading ownership shortcut without expanding the current Phase 0.5 job/event shape

## [0.6.13] - 2026-04-04 21:10:00 +11:00

### Changed
- resident access updates now record `responsibility_owner=coordinator` so booked-access changes land with the coordination role instead of being mis-stamped as triage work
- repo-facing wording now describes FixHub as a civil-works coordination platform being approached through a constrained residence-operations pilot
- package metadata and UI tagline were tightened to remove leftover "minimal MVP" framing

### Notes
- this run kept the current event-backed job model and corrected operational ownership plus repo honesty rather than broadening scope

## [0.6.12] - 2026-04-04 20:05:00 +11:00

### Changed
- contractor assigned-job queues now show only the current dispatch target instead of every historically visible job
- reassigned contractors still retain read-only job detail access through recorded participation history, but those jobs no longer appear in the live execution queue
- related-job summaries now derive status from the event stream so repeat-history panels do not fall back to stale `jobs.status` cache values

### Notes
- this run tightened the distinction between live field responsibility and historical visibility without changing auth, seed flows, or the shared timeline model

## [0.6.11] - 2026-04-04 19:20:00 +11:00

### Changed
- contractor read visibility now follows recorded assignment and participation history instead of only the mutable current `jobs` assignee cache
- contractor write actions now require the current active dispatch target, so reassigned contractors can still read the timeline without mutating live work
- contractor job pages now hide execution controls when a job is visible only through historical participation

### Notes
- this run tightened actor-relationship truth without changing resident auth, demo seed data, or structured location flows

## [0.6.10] - 2026-04-04 14:56:48 +11:00

### Changed
- removed the dead `app.models.mvp` alias module because it no longer reflected any real model boundary in the implemented pilot
- rewrote README and docs index language so the repo is described as a constrained student-living pilot instead of a vague MVP bucket
- cleaned the schema assessment to remove duplicated legacy text and to state more directly what is implemented now versus what remains deferred

### Notes
- this run favored repository honesty and reduction of legacy noise over new feature surface
- validation was attempted after the change set and is reported with the run summary

## [0.6.9] - 2026-04-04 18:35:00 +11:00

### Changed
- contractor job visibility and listing now derive current dispatch access from assignment events before falling back to mutable `jobs` row fields
- added regression coverage for contractor reads when the `jobs` assignment cache drifts away from the recorded timeline

### Notes
- this run aligned access control with the same event-backed assignment truth already used in API projections

## [0.6.8] - 2026-04-04 18:05:00 +11:00

### Changed
- resident location selection now shows structured hierarchy labels instead of bare child-location names
- new jobs store the full hierarchical `location_snapshot`, and job/event reads now prefer that stored snapshot over the mutable current location row
- asset-linked jobs now store `asset_snapshot`, and job/event reads preserve that stored asset label after later catalog renames

### Notes
- this run tightened truthful location and asset context without changing auth, seed, or the existing structured location-id workflow

## [0.6.7] - 2026-04-04 17:10:00 +11:00

### Changed
- job projections now derive dispatch context from explicit assignment events before falling back to mutable job fields
- resident and operations API reads now stay aligned with the recorded assignment history even if the `jobs` row drifts

### Notes
- this run tightened the truthful coordination record without changing the current auth, seed, or structured location flows

## [0.6.6] - 2026-04-04 16:35:00 +11:00

### Changed
- removed the false mutual-exclusion assumption between contractor organisation assignment and named-contractor dispatch
- direct contractor assignment now preserves the contractor organisation automatically and backfills that context for existing direct-user jobs
- updated the operations and resident-facing copy so dispatch shows accountable contractor organisation plus optional named field worker
- refreshed `README.md` and `docs/schema_student_living_assessment.md` to describe the truer org-plus-user dispatch model

### Notes
- this run stayed within the current Phase 0.5 job model and corrected dispatch truth instead of introducing visits or broader workflow splits
- validation was attempted after the change set and is reported with the run summary

## [0.6.5] - 2026-04-04 16:15:00 +11:00

### Changed
- added structured assignment snapshots to `events` so timeline entries keep the responsible organisation or contractor user that was active when the event occurred
- updated README and schema assessment language to describe event-backed responsibility history instead of leaving assignment history implied by mutable job fields

### Notes
- this run focused on a foundational truthfulness improvement rather than new product surface area
- verification focus is migrations plus app and schema coverage around assignment history

## [0.6.4] - 2026-04-04 15:20:00 +11:00

### Changed
- documented that direct contractor dispatch now requires the assignee to belong to a contractor organisation
- updated `README.md` language to describe the repo as a student-living coordination pilot rather than a generic maintenance demo
- updated `docs/schema_student_living_assessment.md` to record the tighter dispatch-credibility guard and the remaining limitation around org-plus-user accountability

### Notes
- this run made a targeted repository-correction pass rather than a broad redesign
- verification focus is the app and projection suite around assignment and timeline behavior

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
- captured assignment target snapshots on events so historical responsibility survives reassignment
