# Chat Context: 2026-03-21

Last updated: `2026-03-21 15:27:59 +11:00`

## Document Metadata

- Owner: `student-living-platform`
- Reviewer: `codex-chat-handoff`
- Status: `active`

## Purpose

This file captures all meaningful work completed in the March 2026 planning and research chat so a new chat can continue without replaying the full thread.

## Scope Of Work Completed

- explored the repo structure, stack, entry points, and test surface
- gathered specialist findings for architecture, auth, migrations, and test coverage
- compared the product direction against AMS, CMMS, CMS, and digital-twin standards/practice
- developed a finalized phased implementation plan
- converted that plan into a quarter-by-quarter roadmap and a GitHub-ready issue backlog
- no repository code was edited in this chat

## Working Assumptions Used In The Chat

- `SD` means software/systems design
- `CMS` means complaint/case management, not content management
- the correct digital-twin target for this codebase is a process-first twin of civil work coordination, not a 3D-first visualization product

## Repo Snapshot Used For Planning

- the repo is a single Python 3.11+ FastAPI application with SQLAlchemy, Alembic, Jinja2, psycopg, and Uvicorn
- the main ASGI entrypoint is `app = create_app()` in [`app/main.py`](../app/main.py)
- the core workflow control plane is centered on [`app/api/jobs.py`](../app/api/jobs.py) and [`app/services/workflow.py`](../app/services/workflow.py)
- shared request/session/auth/visibility/serialization behavior is concentrated in [`app/api/deps.py`](../app/api/deps.py)
- database bootstrap is inconsistent: Alembic is present, but runtime startup still calls `Base.metadata.create_all()` in [`app/main.py`](../app/main.py)
- tests are strongest around the central `PATCH` workflow but weaker on Postgres realism, page auth, visibility boundaries, and some read paths

## Existing Open Product TODOs Observed

- request to work-order split is still open in [`docs/todo_implementation_checklist.md`](todo_implementation_checklist.md)
- structured visits and routing reasons are still open in [`docs/todo_implementation_checklist.md`](todo_implementation_checklist.md)
- the schema assessment still flags the need for a first-class visit/appointment entity in [`docs/schema_student_living_assessment.md`](schema_student_living_assessment.md)

## Specialist Threads And Outcomes

### Initial Repo Exploration

- the app mixes JSON API routes and server-rendered resident/admin/contractor pages in one FastAPI process
- the most important repo surfaces are `app/`, `alembic/`, `tests/`, and `docs/`
- key risk areas identified immediately were `deps.py` as a catch-all, dual schema authority, demo auth, and SQLite-vs-Postgres mismatch

### Architecture Review

- the app factory in [`app/main.py`](../app/main.py) is a good foundation
- the main maintainability problem is boundary collapse into [`app/api/deps.py`](../app/api/deps.py)
- `jobs.py` still owns too much orchestration and transactional behavior
- there is also a confusing split between per-app database lifecycle in [`app/main.py`](../app/main.py) and module-global DB construction in [`app/core/database.py`](../app/core/database.py)
- recommended architecture direction:
- split `deps.py` into identity, authorization/visibility, query, and presenter modules
- move create/assign/transition/event orchestration into application services
- keep [`app/services/workflow.py`](../app/services/workflow.py) as the policy engine

### Auth Review

- API auth currently trusts `X-User-Email`
- page auth can come from query param, header, or cookie selectors
- `/switch-user` sets identity cookie state directly
- auth is demo-friendly but not production-safe
- recommended auth direction:
- remove or gate demo identity flows behind explicit dev mode
- replace raw email identity with a real principal/auth middleware path
- add regression tests for impersonation, selector precedence, and route protection

### Migration Review

- Alembic exists and looks like the intended deployment path
- startup still runs `Base.metadata.create_all()` in normal app boot
- a migration specialist reproduced the collision: a database initialized through app startup then failed `alembic upgrade head` because tables already existed
- recommended migration direction:
- make Alembic the sole non-test schema authority
- add Postgres + Alembic smoke tests
- treat downgrade behavior in later data-heavy revisions as effectively lossy unless reworked

### Test Coverage Review

- a specialist reported `.venv\\Scripts\\python.exe -m pytest -q` as `24 passed in 1.94s` during this chat
- strongest test coverage is around central PATCH lifecycle flows
- weaker areas:
- successful `/api/me` path
- list/read-path behavior
- visibility filters
- page auth and selector precedence
- cancelled/escalated branches
- Postgres + Alembic realism
- recommended test direction:
- add migration smoke coverage
- add auth/visibility/read-path integration tests
- add direct workflow-unit coverage for uncovered branches

### AMS / CMS / CMMS Positioning Review

- current best-fit label is `CMMS-lite`
- there is also a clear `CMS-lite` layer via resident intake and shared timeline/status visibility
- current AMS support is only seed-level because asset and location records do not yet carry true lifecycle, risk, criticality, condition, or strategy data
- recommended product positioning sequence:
- first: civil work coordination CMMS with resident case intake
- next: twin-ready civil work coordination platform
- later: process-first digital twin
- finally: AMS overlay on top of CMMS/CMS + twin coordination

### Digital Twin Standards / Direction Review

- the repo is not a digital twin today
- it is better described as a workflow system or digital operations model with event history and some twin-like primitives
- the correct target is a process-first digital twin of civil work coordination
- the twin should represent:
- assets
- places/zones
- work packages and work orders
- crews and contractors
- permits and dependencies
- service impacts
- planned vs actual progress
- real-world observations synchronized from the field
- main missing twin capabilities:
- live synchronization
- source/freshness/confidence metadata
- spatial intelligence
- external system interfaces
- predictive/decision-support loops
- common semantics / digital thread

## Final Product Positioning From The Chat

- current state: `CMMS-lite + CMS-lite`, not a digital twin, not an AMS
- target state after early phases: `civil work coordination platform with CMMS/CMS workflow`
- target state after mid phases: `twin-ready civil work coordination platform`
- target state after later phases: `process-first digital twin of civil work coordination`
- target state after final phase: `AMS + CMMS + CMS`, with the twin as the operational coordination layer

## Finalized Implementation Plan

### Phase 0: Trust And Control Plane

- remove normal-startup `create_all()` and make Alembic the only non-test schema authority
- isolate or replace demo auth flows
- split [`app/api/deps.py`](../app/api/deps.py)
- move route-level orchestration out of [`app/api/jobs.py`](../app/api/jobs.py)
- add Postgres + Alembic smoke tests
- add auth/visibility regression tests

### Phase 1: Finish The CMMS/CMS Operating Model

- implement `request -> work_order` split
- add first-class `visit` entity
- add routing decision records with reason codes
- add priority, SLA, target date, and stronger closure capture
- add resident acknowledgement, communication history, reopen flow, and case outcomes

### Phase 2: Build The Twin-Ready Information Model

- extend asset and location models with external IDs, hierarchy, spatial references, and lifecycle attributes
- add crew/team, vehicle, permit, inspection, dependency, blockage, and service-impact entities
- add immutable planned-vs-actual operational event streams
- add integration contracts for GIS, BIM/CDE, EAM/ERP, field inspection, and permit/access data

### Phase 3: Become A Digital Shadow

- ingest one-way operational updates from field/mobile, contractors, inspections, permit systems, and relevant telemetry
- add source, freshness, confidence, and tolerance metadata
- add outbox/event streaming and time-series/state-history support

### Phase 4: Become A Process-First Digital Twin

- define the twin object as active civil work packages plus affected assets/locations, crews, permits, constraints, and live status
- add ETA, delay-propagation, resequencing, and conflict-detection services
- add a map/timeline/state coordination UI
- keep humans in the loop for intervention decisions

### Phase 5: Add The AMS Layer

- add asset criticality, condition, risk, consequence, and lifecycle planning
- add maintenance strategy and repair-vs-replace support
- add asset-governance KPIs and dashboards

## Quarter-By-Quarter Roadmap

### Q2 2026 (Apr-Jun 2026)

- harden control plane
- Alembic-only bootstrap
- demo auth isolated or replaced
- `deps.py` refactor started
- Postgres migration smoke tests added

### Q3 2026 (Jul-Sep 2026)

- ship request to work-order split
- ship first-class visit/dispatch model
- add routing decisions, SLA/priority/target-date handling
- add resident acknowledgement and reopen/closure feedback flows

### Q4 2026 (Oct-Dec 2026)

- extend asset/location model for twin-ready semantics
- add crew, permit, inspection, dependency, blockage, and service-impact entities
- define planned-vs-actual operational event model

### Q1 2027 (Jan-Mar 2027)

- build digital-shadow ingestion and synchronization backbone
- integrate at least a small set of real operational feeds
- expose sync freshness/provenance/confidence

### Q2 2027 (Apr-Jun 2027)

- deliver process-first digital twin capabilities
- add predictive coordination services
- add map/timeline coordination UI

### Q3 2027 (Jul-Sep 2027)

- deliver AMS overlay
- add asset governance, risk, and lifecycle decision support
- add portfolio KPIs

## GitHub Backlog Produced In The Chat

### Quarter 1 / Phase 0 Backlog

- `EPIC: Harden control plane for production-safe workflow execution`
- `Remove Base.metadata.create_all() from normal app startup`
- `Add Postgres + alembic upgrade smoke test to test suite`
- `Gate demo identity flows behind explicit dev mode`
- `Replace X-User-Email middleware with pluggable principal provider`
- `Split app/api/deps.py into identity, authorization, queries, and presenters`
- `Move job orchestration out of routes into application services`
- `Add regression tests for page auth selector precedence and route visibility`

### Quarter 2 / Phase 1 Backlog

- `EPIC: Implement request-to-work-order operating model`
- `Add resident Request model and 1:N Request -> WorkOrder relationship`
- `Add Visit model with appointment window, outcome, and access-failure reason`
- `Add routing decision model with structured reason codes`
- `Add priority, SLA target, due date, and closure capture fields`
- `Update resident timeline to aggregate progress across multiple work orders`
- `Add resident acknowledgement, reopen, and closure feedback flow`
- `Add multi-work-order and visit lifecycle tests`

### Quarter 3 / Phase 2 Backlog

- `EPIC: Build twin-ready civil work information model`
- `Add external IDs and source-system attribution to assets and locations`
- `Add site, zone, and worksite hierarchy to location model`
- `Add crew, contractor-team, and vehicle entities`
- `Add permit, inspection, dependency, blockage, and service-impact entities`
- `Add immutable planned-vs-actual operational event stream`
- `Define GIS/BIM/EAM integration contracts and adapter interfaces`

### Quarter 4 / Phase 3 Backlog

- `EPIC: Turn workflow system into a digital shadow`
- `Build ingestion API for field/mobile and contractor acknowledgements`
- `Add sync metadata: source, freshness, confidence, tolerance`
- `Add outbox/event bus for operational state changes`
- `Persist inspection, permit, and access-constraint updates from external feeds`
- `Expose stale or conflicting real-world state in admin/coordinator UI`

### Quarter 5 / Phase 4 Backlog

- `EPIC: Deliver process-first digital twin capabilities`
- `Add ETA and delay-propagation prediction service`
- `Add dependency conflict and resource-contention detection`
- `Add resequencing recommendation engine with human approval`
- `Build map + timeline + state coordination view`
- `Document model assumptions and validation tolerances for twin services`

### Quarter 6 / Phase 5 Backlog

- `EPIC: Add AMS governance layer on top of coordination twin`
- `Add asset condition, criticality, lifecycle state, and consequence fields`
- `Add maintenance strategy and repair-vs-replace decision support`
- `Add portfolio KPIs: MTTR, repeat failures, preventive/reactive ratio, risk exposure`
- `Build asset-governance dashboard for portfolio and campus views`

## Key Facts A New Chat Should Preserve

- no code changes were made in this chat
- planning output is intentionally sequenced so product expansion does not outrun platform hardening
- the shortest credible path agreed in the chat is:
- trustworthy CMMS/CMS core
- then twin-ready information model
- then digital shadow
- then process-first digital twin
- then AMS overlay
- the open repo TODOs already align with the first substantive product quarter: request/work-order split and structured visits

## External References Used In The Chat

- [NIST Essential Elements](https://www.nist.gov/digital-twins/essential-elements)
- [NIST Digital Twin Standardization](https://www.nist.gov/digital-twins/digital-twin-standardization)
- [ISO 23247-1](https://www.iso.org/standard/75066.html)
- [NDTP Digital Twin Definition](https://ndtp.co.uk/digital-twin-definition/)
- [Digital Twin Consortium Glossary](https://www.digitaltwinconsortium.org/glossary/glossary/)
- [Digital Twin Consortium Capabilities](https://www.digitaltwinconsortium.org/initiatives/capabilities-periodic-table/)
- [ISO 55000 / 55001 / 55002 family](https://committee.iso.org/home/tc251)
- [ISO 10002](https://www.iso.org/standard/71580.html)
- [IBM work order process reference](https://www.ibm.com/think/insights/work-order-process)

## Suggested First Prompt For A New Chat

Use `docs/chat_context_2026-03-21.md` as the working handoff. Start by confirming whether we want to execute `Phase 0`, refine the backlog into milestone-ready GitHub issue bodies, or begin implementing the `request -> work_order` and `visit` model changes from the existing TODO docs.
