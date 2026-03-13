# Development

| Metadata | Value |
| --- | --- |
| Docs version | 0.2.0 |
| Status | Active |
| Owner | Developer experience maintainer |
| Reviewers | Project maintainer; docs maintainer |
| Last updated | 2026-03-13 |
| Review cadence | On change and quarterly |

## Current State (Implemented)

## Prerequisites

- Python 3.11+
- PostgreSQL 14+
- `DATABASE_URL` pointing at local development DB

Example:

```bash
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/fixhub
```

`app/core/config.py` includes a local fallback `DATABASE_URL` for development use only.

## Install

```bash
python -m venv .venv
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

Windows PowerShell activation:

```powershell
.venv\Scripts\Activate.ps1
```

## Migrations

```bash
alembic upgrade head
```

## Seed and Smoke Test

```bash
python -m scripts.seed_mvp
python -m scripts.smoke_test_mvp
```

## Quality Checks

```bash
pytest -q
ruff check .
ruff format .
mypy app
bandit -r app
pip-audit
```

## Documentation Process Guidance

Current process expectations:
- Update docs in the same change where behavior changes.
- Keep "Current State" sections strictly implementation-backed.
- Add future ideas only in `TODO (Proposed)` lists.
- Record docs-set version changes in [`CHANGELOG.md`](CHANGELOG.md).
- Capture design/model decisions in [`adr/README.md`](adr/README.md) when they materially shape the codebase.
- Keep owner/reviewer metadata current when document responsibility changes.

## Documentation Versioning Rules

The documentation set uses semantic versioning:
- Major: structural reset or policy change across the docs set.
- Minor: new maintained documents, ADRs, or significant process additions.
- Patch: factual corrections, clarifications, or current-state sync updates.

## TODO (Proposed)

- TODO: Add `make`/task runner commands to unify setup and checks across OS environments.
- TODO: Add contributor checklist for migrations + tests + docs update requirements.
- TODO: Add CI status and required checks once CI pipeline exists.

## SD Documentation Sanity Check

Aligned:
- Reproducible setup steps exist.
- Validation commands are explicit.
- Docs versioning and decision logging rules are now documented.

Gaps:
- No automated review reminder flow for the declared document cadence.
- No repo-level PR template yet enforcing doc version/changelog updates when needed.

## Feedback on Documentation Process

- The docs now separate facts from proposals, which reduces implementation ambiguity.
- The process is stronger with versioning and ADRs, but it still depends on manual discipline.

## Change Log

- 2026-03-13 15:52:00 +11:00 (Australia/Sydney): Added docs versioning rules, ADR guidance, and ownership metadata.
- 2026-03-13 15:21:56 +11:00 (Australia/Sydney): Reorganized development doc with process guidance, TODOs, and SD-practice checks.
