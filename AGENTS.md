# AGENTS.md

## Repository expectations
- Before editing, run `git status --short`.
- If the worktree is dirty, do not edit tracked files.
- Do not commit.
- Do not assume `python`, `pip`, `pytest`, `alembic`, or `uvicorn` are on `PATH`.
- Prefer the repo-local interpreter at `.\.venv\Scripts\python.exe` for Python tooling commands.
- Use `.\.venv\Scripts\python.exe -m pytest`, never bare `pytest`.
- For Python validation, run in this order:
  1. `.\.venv\Scripts\python.exe -m pip install -e .`
  2. `.\.venv\Scripts\python.exe -m pip install pytest`
  3. `.\.venv\Scripts\python.exe -m pytest --version`
  4. `.\.venv\Scripts\python.exe -m pytest`
- Avoid network-dependent tests.
- Prefer the smallest safe fix.
- Do not remove previous logs.
- Update README diagrams only when they reflect current implemented behavior.
