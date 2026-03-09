# Development

## Prerequisites

- Python 3.11+
- PostgreSQL 14+
- `DATABASE_URL` pointing at a local development database

Example:

```bash
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/fixhub
```

The default `DATABASE_URL` in [`app/core/config.py`](/C:/Users/halan/PycharmProjects/fixhub-v1/app/core/config.py:8) is for local development only.

## Install

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

On Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

## Migrations

Alembic is configured through [`alembic.ini`](/C:/Users/halan/PycharmProjects/fixhub-v1/alembic.ini). `DATABASE_URL` overrides the URL from the ini file at runtime.

```bash
alembic upgrade head
```

## Seed and smoke workflow

```bash
python -m scripts.seed_mvp
python -m scripts.smoke_test_mvp
```

The seed script rewrites the development users with known dev passwords on each run.

## Quality checks

```bash
pytest -q
ruff check .
ruff format .
mypy app
bandit -r app
pip-audit
```

`pytest` is configured via [`pytest.ini`](/C:/Users/halan/PycharmProjects/fixhub-v1/pytest.ini) to use `--basetemp=.pytest-tmp` instead of the shared default temp tree.
