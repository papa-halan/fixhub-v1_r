# FixHub MVP

FixHub is a maintenance workflow demo for a resident -> operations -> contractor lifecycle.

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
        text location_detail_text
        enum status
        uuid created_by FK
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
        uuid location_id FK
        uuid asset_id FK
        enum event_type
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
    ORGANISATIONS ||--o{ JOBS : owns
    LOCATIONS ||--o{ JOBS : reported_at
    ASSETS ||--o{ JOBS : reported_on
    ORGANISATIONS ||--o{ JOBS : assigned_org
    USERS ||--o{ JOBS : direct_assignee
    USERS ||--o{ JOBS : creates
    JOBS ||--o{ EVENTS : has
```

Reportable operational locations are managed child `space` or `unit` rows. Root-level legacy placeholders are excluded from the active catalog.

## Current Workflow

1. A resident signs in and submits a report against a managed location in their organisation.
2. The report may reference a known asset at that location, but asset capture is optional.
3. Front desk or operations staff add clarifying notes when needed.
4. A dispatch coordinator assigns the work to a contractor organisation or a direct contractor.
5. A property manager triages and schedules the job.
6. The assigned contractor or technician moves the work through execution states.
7. Everyone reads the same shared timeline with stable location context and optional asset context.

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
| Indy Independent Contractor | `contractor` | `independent.contractor@fixhub.test` |

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
