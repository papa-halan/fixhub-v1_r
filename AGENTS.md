# AGENTS.md

## Repository expectations
- Before editing, run `git status --short`.
- If the worktree is dirty, do not edit tracked files.
- Do not commit.
- Do not assume `pytest` CLI exists.
- Use `python -m pytest`, never bare `pytest`.
- For Python validation, run in this order:
  1. `python -m pip install -e .`
  2. `python -m pip install pytest`
  3. `python -m pytest --version`
  4. `python -m pytest`
- Avoid network-dependent tests.
- Prefer the smallest safe fix.
- Do not remove previous logs.
- Update README diagrams only when they reflect current implemented behavior.