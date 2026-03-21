# FixHub MVP

FixHub is a maintenance workflow demo for a resident -> operations -> contractor lifecycle. Phase 0 stabilizes boot, schema authority, and auth boundaries. Phase 0.5 adds the minimum organisation and location structure needed to keep the current reporting flow valid without starting the larger Phase 1 request/work-order split.

## Phase 0 Status

- Alembic migrations are the schema authority.
- App startup fails fast if the database is not at Alembic head.
- Runtime does not call `Base.metadata.create_all()`.
- Auth is password login plus signed cookie sessions.
- Demo users and shortcut switching are available only when `FIXHUB_DEMO_MODE=1`.

## Phase 0.5 Foundation

- `users.organisation_id` is the primary org boundary for the current deployment.
- `locations` belong to an organisation and now support `parent_id` plus typed hierarchy (`site`, `building`, `space`, `unit`).
- `jobs.organisation_id` is stored directly.
- Resident report creation uses `location_id` as the operational source of truth.
- `location_detail_text` is optional descriptive text only.
- Resident and operations access stays org-scoped, while contractor visibility stays tied to explicit dispatch.

## Current Workflow

- residents sign in and create a job against a managed location in their organisation
- operations users coordinate intake, triage, scheduling, escalation, and follow-up
- contractors move work through execution states
- everyone reads the same shared timeline, with typed event metadata and stable location context

## Roles

- `resident`
- `admin`
- `reception_admin`
- `triage_officer`
- `coordinator`
- `contractor`

## Data Model

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

## Lifecycle

```mermaid
stateDiagram-v2
    [*] --> new
    new --> assigned
    assigned --> triaged
    triaged --> scheduled
    scheduled --> in_progress
    in_progress --> completed

    assigned --> on_hold
    triaged --> on_hold
    scheduled --> on_hold
    in_progress --> on_hold
    in_progress --> blocked

    assigned --> escalated
    triaged --> escalated
    scheduled --> escalated
    in_progress --> escalated

    completed --> reopened
    completed --> follow_up_scheduled
    follow_up_scheduled --> in_progress
    reopened --> triaged

    cancelled --> [*]
```

## Guard Conditions

| Rule | Applies to | Effect |
| --- | --- | --- |
| Assignee required | `assigned`, `scheduled`, `in_progress`, `blocked`, `completed`, `follow_up_scheduled` | Transition is rejected unless `assigned_org_id` or `assigned_contractor_user_id` is set |
| Assignment exclusivity | assignment updates | `assigned_org_id` and `assigned_contractor_user_id` cannot both be non-null |
| Assignment clear rollback | clearing the last assignee without an explicit status change | job moves back to `new` or `triaged` instead of staying unassigned in an execution state |
| Triage permission | `triaged`, `scheduled`, `follow_up_scheduled` | only `triage_officer` or `admin` can move jobs into these states |
| Assignment permission | assignment field changes | only `coordinator` or `admin` can change dispatch target |
| Completion accountability | `completed` | completion requires explicit accountability metadata |
| Same-org report validation | resident report creation | `location_id` must belong to the acting user organisation and be a reportable location type |

## Auth And Demo Mode

- `POST /login` verifies a scrypt-hashed password and sets a signed `HttpOnly` session cookie.
- Protected pages redirect back to `/` when the session is missing or invalid.
- Demo shortcuts (`/switch-user` and the “View as” UI) are available only when `FIXHUB_DEMO_MODE=1`.
- Demo-seeded databases should be treated as disposable local/demo environments, not promoted into default or production operation.

Seeded demo users when demo mode is enabled:
- `resident@fixhub.test`
- `admin@fixhub.test`
- `reception@fixhub.test`
- `triage@fixhub.test`
- `coordinator@fixhub.test`
- `contractor@fixhub.test`
- `maintenance.contractor@fixhub.test`
- `independent.contractor@fixhub.test`

Seeded demo organisations:
- `University of Newcastle`
- `Student Living`
- `Newcastle Plumbing`
- `Campus Maintenance`
- `Independent Contractors`

Shared demo password:
- `fixhub-demo-password`

## API Examples

### Create A Resident Report

```json
POST /api/jobs
{
  "title": "Leaking bathroom tap",
  "description": "Water is pooling under the sink.",
  "location_id": "0d7dfe26-8a4f-4dd6-8758-ae8bbdd1839f",
  "location_detail_text": "Near the bathroom door",
  "asset_name": "Sink"
}
```

### Dispatch Directly To An Independent Contractor

```json
PATCH /api/jobs/{job_id}
{
  "assigned_contractor_user_id": "2b53b4e8-6c72-4e89-9a3c-1bc7b9150b53"
}
```

### Contractor Completes Work

```json
PATCH /api/jobs/{job_id}
{
  "status": "completed",
  "responsibility_stage": "execution"
}
```

## Run Modes

### Local SQLite Demo

```powershell
pip install -e .[dev]
$env:FIXHUB_DEMO_MODE = "1"
alembic upgrade head
uvicorn app.main:app --reload
```

### Local App + Docker Postgres

```powershell
pip install -e .[dev]
docker compose up db -d
$env:DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/fixhub"
$env:FIXHUB_DEMO_MODE = "1"
alembic upgrade head
uvicorn app.main:app --reload
```

### Full Docker Stack

```powershell
docker compose up --build
```

### Production-Style Manual Run

```powershell
$env:DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/fixhub"
$env:FIXHUB_DEMO_MODE = "0"
$env:FIXHUB_SEED_DEMO_DATA = "0"
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Documentation

- docs index: [docs/README.md](docs/README.md)
- architecture notes: [docs/architecture.md](docs/architecture.md)
- schema assessment: [docs/schema_student_living_assessment.md](docs/schema_student_living_assessment.md)
- docs changelog: [docs/CHANGELOG.md](docs/CHANGELOG.md)

## Verification

Current implementation was verified with:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```
