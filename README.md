# FixHub MVP

FixHub is a small maintenance-log app built around two entities: `jobs` and `events`.

The live concept is simple:
- residents create jobs
- admins assign contractor organisations
- contractors add updates and complete work
- everyone reads the same event timeline

## Scope

Database tables:
- `users`
- `organisations`
- `jobs`
- `events`

API routes:
- `GET /api/me`
- `POST /api/jobs`
- `GET /api/jobs`
- `GET /api/jobs/{job_id}`
- `PATCH /api/jobs/{job_id}`
- `GET /api/jobs/{job_id}/events`
- `POST /api/jobs/{job_id}/events`

Pages:
- `/resident/report`
- `/resident/jobs`
- `/resident/jobs/{job_id}`
- `/admin/jobs`
- `/admin/jobs/{job_id}`
- `/contractor/jobs`
- `/contractor/jobs/{job_id}`

## Demo users

The app seeds three users on startup:
- `resident@fixhub.test`
- `admin@fixhub.test`
- `contractor@fixhub.test`

In the browser, use the top-right switcher to jump between them.

For API calls, set `X-User-Email` to one of those addresses.

## Database defaults

Both local `uvicorn` and Docker use the same PostgreSQL database by default.

Connection values:
- database: `fixhub`
- user: `postgres`
- password: `postgres`
- port: `5432`

Hostname depends on where the app is running:
- host machine: `localhost`
- Docker app container: `db`

## Run modes

Choose one app mode at a time.

### Mode 1: local app + Docker Postgres

Use this when you want live code reload from your workstation.

```powershell
pip install -e .[dev]
docker compose up db -d
uvicorn app.main:app --reload
```

The local app connects to:

```text
postgresql+psycopg://postgres:postgres@localhost:5432/fixhub
```

Open: [http://localhost:8000](http://localhost:8000)

Important:
- run only the `db` service here, not the Docker `app` service
- if Docker `app` is already running, stop it first with `docker compose stop app`
- otherwise port `8000` is already occupied by Docker and you will not be talking to your local `uvicorn`

### Mode 2: full Docker stack

```powershell
docker compose up --build
```

The Docker app container connects to:

```text
postgresql+psycopg://postgres:postgres@db:5432/fixhub
```

Open: [http://localhost:8000](http://localhost:8000)

### Mode 3: local app on a different port while Docker app is running

If you intentionally want both app processes running:

```powershell
uvicorn app.main:app --reload --port 8001
```

Open the local host app at [http://localhost:8001](http://localhost:8001)

## Production-style manual run

```powershell
$env:DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/fixhub"
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Documentation

- docs index: [docs/README.md](docs/README.md)
- schema assessment: [docs/schema_student_living_assessment.md](docs/schema_student_living_assessment.md)
- docs changelog: [docs/CHANGELOG.md](docs/CHANGELOG.md)

## Development Change Log (Implemented)

Timestamp: `2026-03-13 23:17:31 +11:00`

- default database URL changed from SQLite to PostgreSQL in `app/core/config.py`.
- `docker-compose.yml` now sets `FIXHUB_DEFAULT_USER` for deterministic demo user startup.
- frontend forms now declare `method="post"` in resident/admin/contractor templates.
- base template loads `/static/app.js` without `defer` for form wiring consistency.
- test coverage adds `test_report_page_wires_post_form` to verify script and POST form wiring.

## Documentation TODO (Proposed)

- add a dedicated architecture diagram for data flow between role pages and API routes.
- add a repeatable docs review checklist to CI once the project has a stable lint/test environment.
- add environment bootstrap notes for Windows Python installations to avoid `encodings` startup failures during test runs.

## Notes

- The app auto-seeds demo organisations and users.
- The UI is server-rendered and reuses one `EventTimeline` partial across roles.
- Authentication is intentionally lightweight for the demo: cookie switching in the UI, `X-User-Email` for API use.

## Troubleshooting

- `localhost:8000` shows pages but new jobs do not appear:
  You are probably hitting a different app process than the one you think you started. Check whether Docker `app` is already bound to port `8000`.
- local `uvicorn` cannot connect to the database:
  Make sure `docker compose up db -d` is running and Postgres is listening on `localhost:5432`.
- Docker app cannot connect to the database:
  Inside Compose, the hostname must be `db`, not `localhost`.
