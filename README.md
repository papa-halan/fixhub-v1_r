# FixHub MVP

FixHub is a maintenance workflow demo for a resident -> operations -> contractor lifecycle. The current model supports Student Living-style triage, scheduling, direct independent-contractor dispatch, organisation-backed contractor dispatch, and accountability metadata on timeline events.

## Current Workflow

- residents create jobs with remembered `location` and `asset` context
- operations users coordinate intake, triage, scheduling, escalation, and follow-up
- contractors move work through execution states
- everyone reads the same shared timeline, now with typed event metadata

## Roles

- `resident`
- `admin`
- `reception_admin`
- `triage_officer`
- `coordinator`
- `contractor`

## Scope

Database tables:
- `locations`
- `assets`
- `users`
- `organisations`
- `jobs`
- `events`

Core API routes:
- `GET /api/me`
- `POST /api/jobs`
- `GET /api/jobs`
- `GET /api/jobs/{job_id}`
- `PATCH /api/jobs/{job_id}`
- `GET /api/jobs/{job_id}/events`
- `POST /api/jobs/{job_id}/events`

Server-rendered pages:
- `/resident/report`
- `/resident/jobs`
- `/resident/jobs/{job_id}`
- `/admin/jobs`
- `/admin/jobs/{job_id}`
- `/contractor/jobs`
- `/contractor/jobs/{job_id}`

## Code Layout

- `app/models/`: SQLAlchemy persistence models and enums
- `app/schema/`: Pydantic request and response contracts
- `app/services/`: demo data and catalog helpers
- `app/api/`: API and page routers plus shared dependency helpers
- `alembic/versions/`: schema migrations

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
        enum role
        uuid organisation_id FK
        timestamptz created_at
    }

    LOCATIONS {
        uuid id PK
        uuid organisation_id FK
        text name
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
        enum status
        uuid created_by FK
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
        timestamptz created_at
    }

    ORGANISATIONS ||--o{ ORGANISATIONS : parent_of
    ORGANISATIONS ||--o{ USERS : has
    ORGANISATIONS ||--o{ LOCATIONS : owns
    LOCATIONS ||--o{ ASSETS : contains
    LOCATIONS ||--o{ JOBS : reported_at
    ASSETS ||--o{ JOBS : reported_on
    ORGANISATIONS ||--o{ JOBS : assigned_org
    USERS ||--o{ JOBS : direct_assignee
    USERS ||--o{ JOBS : creates
    JOBS ||--o{ EVENTS : has
```

## Lifecycle

### Business-Level State Diagram

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

### Guard Conditions And Side Effects

| Rule | Applies to | Effect |
| --- | --- | --- |
| Assignee required | `assigned`, `scheduled`, `in_progress`, `blocked`, `completed`, `follow_up_scheduled` | Transition is rejected unless `assigned_org_id` or `assigned_contractor_user_id` is set |
| Assignment exclusivity | assignment updates | `assigned_org_id` and `assigned_contractor_user_id` cannot both be non-null |
| Assignment clear rollback | clearing the last assignee without an explicit status change | job moves back to `new` or `triaged` instead of remaining unassigned in an execution state |
| Triage permission | `triaged`, `scheduled`, `follow_up_scheduled` | only `triage_officer` or `admin` can move jobs into these states |
| Assignment permission | assignment field changes | only `coordinator` or `admin` can change dispatch target |
| Execution permission | `in_progress`, `blocked`, `completed` | contractor handles normal execution updates; admin completion requires a `reason_code` |
| Accountability metadata | `on_hold`, `blocked`, `cancelled`, `reopened`, `follow_up_scheduled`, `escalated` | `reason_code` is required and the resulting event stores `event_type`, `responsibility_stage`, and `owner_scope` |

## Assignment Semantics

- `assigned_org_id` is for organisation-backed dispatch
- `assigned_contractor_user_id` is for direct contractor dispatch, including independent contractors
- the two assignment fields are mutually exclusive
- the `assigned` status is now an explicit lifecycle state, not a synonym for “has an org assignment”
- contractor visibility covers jobs assigned to their organisation or directly to their user record

## API Examples

### Create A Resident Report

```json
POST /api/jobs
{
  "title": "Leaking bathroom tap",
  "description": "Water is pooling under the sink.",
  "location": "Block A Room 14",
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

### Schedule A Visit After Triage

```json
PATCH /api/jobs/{job_id}
{
  "status": "scheduled"
}
```

### Contractor Completes Work

```json
PATCH /api/jobs/{job_id}
{
  "status": "completed"
}
```

### Schedule A Follow-Up After Completion

```json
PATCH /api/jobs/{job_id}
{
  "status": "follow_up_scheduled",
  "reason_code": "resident_reported_recurrence"
}
```

### Example Job Response Fields

```json
{
  "status": "assigned",
  "assigned_org_id": null,
  "assigned_contractor_user_id": "2b53b4e8-6c72-4e89-9a3c-1bc7b9150b53",
  "assigned_contractor_name": "Indy Independent",
  "assignee_scope": "user",
  "assignee_label": "Indy Independent"
}
```

### Example Timeline Event Fields

```json
{
  "event_type": "assignment",
  "message": "Assigned Indy Independent",
  "reason_code": null,
  "responsibility_stage": "triage",
  "owner_scope": "user"
}
```

## Demo Users

Seeded users:
- `resident@fixhub.test`
- `admin@fixhub.test`
- `reception@fixhub.test`
- `triage@fixhub.test`
- `coordinator@fixhub.test`
- `contractor@fixhub.test`
- `maintenance.contractor@fixhub.test`
- `independent.contractor@fixhub.test`

Seeded organisations:
- `University of Newcastle`
- `Student Living` (child of `University of Newcastle`)
- `Newcastle Plumbing` (`external_contractor`)
- `Campus Maintenance` (`maintenance_team`)

## Run Modes

### Local App + Docker Postgres

```powershell
pip install -e .[dev]
docker compose up db -d
uvicorn app.main:app --reload
```

Open: [http://localhost:8000](http://localhost:8000)

### Full Docker Stack

```powershell
docker compose up --build
```

### Production-Style Manual Run

```powershell
$env:DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/fixhub"
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
python -m pytest tests\test_schema.py tests\test_app.py
```
