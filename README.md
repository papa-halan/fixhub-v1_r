# FixHub Pilot

FixHub is being built toward a civil-works coordination platform. The implemented repo is still a constrained residence-operations pilot, not a generic maintenance suite and not yet a broader civil-works system.

The implemented core is a shared job timeline across resident -> operations -> contractor actors, with structured location context, auditable lifecycle events, dispatch that can preserve both the contractor organisation and the named field worker, and intake records that now distinguish resident-portal reports from staff-mediated entry paths.

This repo is one truthful pilot wedge toward that larger goal. It is strongest where it records who reported work, where it sits, who it was handed to, how access and scheduling changed, and how lifecycle updates accumulated over time. It does not yet model the broader civil-works coordination shape such as separate requests, work orders, visits, routing decisions, or public-sector network coordination.
The seeded demo footprint is intentionally narrower than a campus-wide estate: it stays focused on a small Callaghan residence wedge with a limited contractor set, rather than implying a generic contractor marketplace or broad asset-management rollout.

The repository is currently stabilized through Phase 0.5:

- Alembic migrations are the schema authority.
- App startup fails fast if the database is not at Alembic head.
- Runtime does not call `Base.metadata.create_all()`.
- Auth uses password login plus signed cookie sessions.
- Demo shortcuts are available only when `FIXHUB_DEMO_MODE=1`.
- Reports use a structured `location_id`; free text stays descriptive-only in `location_detail_text`.
- Asset linkage is optional and only attaches to pre-existing location assets; report intake does not invent new structured assets from free text.
- Organisation scoping is enforced for residents and operations users.

Phase 1 is still deferred. This repo does not yet implement the larger request -> work-order -> visit/dispatch split.

## Operational Roles

- `resident`: reporter / occupant who submits and tracks their own reports
- `reception_admin`: front desk / intake user who can log notes and clarify details
- `triage_officer`: property manager who triages and schedules work
- `coordinator`: dispatch coordinator who assigns and reroutes operational work
- `contractor`: contractor or maintenance technician who performs execution updates
- `admin`: system admin account for environment/bootstrap/admin oversight

## Current Data Model

```mermaid
erDiagram
    ORGANISATIONS {
        uuid id PK
        text name UK
        enum type
        uuid parent_org_id FK
        enum contractor_mode
        timestamptz created_at
    }

    USERS {
        uuid id PK
        text name
        text email UK
        text password_hash
        enum role
        bool is_demo_account
        uuid organisation_id FK
        uuid home_location_id FK
        timestamptz created_at
    }

    LOCATIONS {
        uuid id PK
        uuid organisation_id FK
        uuid parent_id FK
        text name
        enum type
        timestamptz created_at
    }

    ASSETS {
        uuid id PK
        uuid location_id FK
        text name
        timestamptz created_at
    }

    JOBS {
        uuid id PK
        text title
        text description
        text location_snapshot
        text asset_snapshot
        text location_detail_text
        enum status
        uuid created_by FK
        uuid reported_for_user_id FK
        uuid organisation_id FK
        uuid location_id FK
        uuid asset_id FK
        uuid assigned_org_id FK
        uuid assigned_contractor_user_id FK
        timestamptz created_at
        timestamptz updated_at
    }

    EVENTS {
        uuid id PK
        uuid job_id FK
        uuid actor_user_id FK
        uuid actor_org_id FK
        uuid assigned_org_id FK
        uuid assigned_contractor_user_id FK
        uuid location_id FK
        uuid asset_id FK
        enum event_type
        enum target_status
        text message
        text reason_code
        enum responsibility_stage
        enum owner_scope
        enum responsibility_owner
        timestamptz created_at
    }

    ORGANISATIONS ||--o{ ORGANISATIONS : parent_of
    ORGANISATIONS ||--o{ USERS : has
    ORGANISATIONS ||--o{ LOCATIONS : owns
    LOCATIONS ||--o{ LOCATIONS : contains
    LOCATIONS ||--o{ ASSETS : contains
    LOCATIONS ||--o{ USERS : anchors
    ORGANISATIONS ||--o{ JOBS : owns
    LOCATIONS ||--o{ JOBS : reported_at
    ASSETS ||--o{ JOBS : reported_on
    ORGANISATIONS ||--o{ JOBS : assigned_org
    USERS ||--o{ JOBS : reported_for
    USERS ||--o{ JOBS : direct_assignee
    USERS ||--o{ JOBS : creates
    JOBS ||--o{ EVENTS : has
```

Reportable operational locations are managed child `space` or `unit` rows. Root-level legacy placeholders are excluded from the active catalog, and resident-facing location selection now shows the structured hierarchy path instead of a flattened room label. Residents are now anchored to a home location so the resident portal only offers physically related places instead of the entire organisation-wide catalog.

## Current Workflow

1. A resident can submit a report through the portal, or operations staff can log the issue on the resident's behalf through a structured intake channel such as office-hours staff intake, after-hours support, or inspection / housekeeping rounds.
2. The report may reference a known asset at that location, but asset capture is optional.
3. The resident remains the visible case owner, while the first `report_created` event records who actually logged the issue and which intake channel it entered through.
4. Front desk or operations staff add clarifying notes when needed.
5. A dispatch coordinator assigns the work to a contractor organisation, and may also name a specific contractor while keeping that contractor organisation attached.
6. A property manager triages and schedules the job.
7. If an organisation-level dispatch is still unnamed when a contractor first starts posting field progress, the timeline now records an explicit assignment event naming that attending contractor before the field note or lifecycle move lands.
8. Only the currently dispatched contractor or maintenance team sees the job in the active contractor queue; earlier assignees keep read-only historical access on the detail view.
9. Everyone reads the same shared timeline with stable location context, optional asset context, assignment snapshots on each event, and clearer intake provenance for resident-visible jobs.

Job reads keep a stored `location_snapshot` so later location renames do not rewrite the historical record for reports and timeline events. Asset-linked jobs now also keep an `asset_snapshot` so later catalog renames do not silently rewrite earlier operational records. Structured `location_id` and `asset_id` remain the relational source of truth for filtering and lookup.

`jobs.created_by` now records who actually logged the coordination record, while `jobs.reported_for_user_id` keeps the resident the work belongs to. That keeps staff-mediated intake truthful without breaking resident-scoped visibility.

Timeline events carry both lifecycle intent (`target_status`) and the active assignment target at the time of the update. The `jobs` row still keeps the current assignee and cached status for filtering, but the event stream is the more truthful record of what happened and who the work was pointed at when it happened.
When execution begins from an organisation-only dispatch, the first contractor-authored field update now creates a visible assignment event that captures the named attendee instead of silently leaving field ownership ambiguous.
Current job reads now also derive assignee labels from the latest assignment event snapshot, so later renames of contractor organisations or field workers do not silently rewrite the dispatch record people coordinated from. Pending-signal and visit-plan summaries use the same event snapshots for actor names, roles, and organisations, so later account edits do not silently rewrite who posted the coordination update people are reacting to.
Organisation-level dispatch remains a valid pilot truth. FixHub can record a booked visit against a contractor organisation without pretending operations already know the exact field worker who will attend.

Resident updates are intentionally narrow. The pilot accepts only structured resident coordination reasons that operations can act on consistently: `resident_access_update`, `resident_access_issue`, `issue_still_present`, `resident_reported_recurrence`, and `resident_confirmed_resolved`. Access reasons are valid only while coordination is still active; post-visit reasons are valid only after completion or during a recorded follow-up cycle.

Supported job states:

- `new`
- `assigned`
- `triaged`
- `scheduled`
- `in_progress`
- `on_hold`
- `blocked`
- `completed`
- `cancelled`
- `reopened`
- `follow_up_scheduled`
- `escalated`

## Auth And Run Modes

## Local Migrations

Alembic now resolves the database target the same way as app startup:

- if `DATABASE_URL` is set, both Alembic and the app use it
- if `DATABASE_URL` is unset, both use the repo-local SQLite database at `fixhub.db`
- `FIXHUB_DEMO_MODE` controls demo seeding and UI shortcuts only; it does not switch databases
- Postgres targets default to `connect_timeout=5` unless `DATABASE_URL` already provides one

For the default local SQLite workflow:

```powershell
pip install -e .[dev]
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
$env:FIXHUB_DEMO_MODE = "1"
alembic upgrade head
```

For a local Postgres workflow, start the database first and set `DATABASE_URL` explicitly:

```powershell
docker compose up db
$env:DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/fixhub"
$env:FIXHUB_DEMO_MODE = "1"
alembic upgrade head
```

### Demo Mode

Use demo mode for local verification with seeded organisations, users, locations, and assets.

```powershell
pip install -e .[dev]
$env:FIXHUB_DEMO_MODE = "1"
alembic upgrade head
uvicorn app.main:app --reload
```

When demo mode is enabled:

- demo users are seeded if `FIXHUB_SEED_DEMO_DATA=1` or left implicit by demo mode
- the login page shows local demo shortcuts
- `/switch-user` is available for seeded demo accounts only

#### Seeded Login Details

When `FIXHUB_DEMO_MODE=1`, the app seeds these demo users. All demo accounts use the shared password `fixhub-demo-password`.

| Name | Role | Email |
| --- | --- | --- |
| Riley Resident | `resident` | `resident@fixhub.test` |
| Sky System Admin | `admin` | `admin@fixhub.test` |
| Fran Front Desk | `reception_admin` | `reception@fixhub.test` |
| Priya Property Manager | `triage_officer` | `triage@fixhub.test` |
| Casey Dispatch Coordinator | `coordinator` | `coordinator@fixhub.test` |
| Devon Contractor | `contractor` | `contractor@fixhub.test` |
| Maddie Maintenance Technician | `contractor` | `maintenance.contractor@fixhub.test` |

### Normal Mode

Use normal mode when you want real password login without demo shortcuts.

On a fresh database, provide a one-time bootstrap user via environment variables:

```powershell
pip install -e .[dev]
$env:FIXHUB_DEMO_MODE = "0"
$env:FIXHUB_SEED_DEMO_DATA = "1"
$env:FIXHUB_BOOTSTRAP_USER_EMAIL = "ops.admin@example.com"
$env:FIXHUB_BOOTSTRAP_USER_PASSWORD = "change-me-now"
$env:FIXHUB_BOOTSTRAP_USER_NAME = "Operations Admin"
$env:FIXHUB_BOOTSTRAP_USER_ORG_NAME = "Harbour Housing"
alembic upgrade head
uvicorn app.main:app --reload
```

The normal-mode bootstrap user is seeded only when both `FIXHUB_BOOTSTRAP_USER_EMAIL` and `FIXHUB_BOOTSTRAP_USER_PASSWORD` are set. That account logs in with the exact email and password values you provide. In the example above, the bootstrap login is `ops.admin@example.com` with password `change-me-now`.

If you also set `FIXHUB_SEED_DEMO_DATA=1`, all seeded demo users listed above are created in normal mode as well, and they can sign in through the normal login form with `fixhub-demo-password`. Demo shortcuts and `/switch-user` still stay disabled unless `FIXHUB_DEMO_MODE=1`.

Optional:

- set `FIXHUB_SEED_DEMO_DATA = "0"` if you want a bootstrap-only normal-mode environment
- `FIXHUB_BOOTSTRAP_USER_ROLE` defaults to `admin`
- `FIXHUB_SESSION_SECRET` should be set explicitly outside disposable local environments

### Docker Demo Stack

`docker compose up --build` starts the local demo stack. It is a demo-first path, not the normal-mode path.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Documentation

- docs index: [docs/README.md](docs/README.md)
- architecture notes: [docs/architecture.md](docs/architecture.md)
- schema assessment: [docs/schema_student_living_assessment.md](docs/schema_student_living_assessment.md)
- docs changelog: [docs/CHANGELOG.md](docs/CHANGELOG.md)
- handoff context: [docs/chat_context_2026-03-21.md](docs/chat_context_2026-03-21.md)
