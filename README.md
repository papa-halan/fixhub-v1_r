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

## Local run

Quick smoke run with SQLite:

```powershell
pip install -e .[dev]
uvicorn app.main:app --reload
```

Production-style run with PostgreSQL:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/fixhub"
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Docker

```powershell
docker compose up --build
```

That starts PostgreSQL plus the backend on port `8000`.

## Notes

- The app auto-seeds demo organisations and users.
- The UI is server-rendered and reuses one `EventTimeline` partial across roles.
- Authentication is intentionally lightweight for the demo: cookie switching in the UI, `X-User-Email` for API use.
