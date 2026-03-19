# Known Issues

Last updated: `2026-03-19 14:26:43 +11:00`

## Document Metadata

- Owner: `student-living-platform`
- Reviewer: `schema-test-automation`
- Status: `active`

## Python Runtime Launch Blocker

### Symptom

Test and dependency commands fail in this environment:

- `python --version` -> `The term 'python' is not recognized...`
- `py --version` -> `The term 'py' is not recognized...`
- `.venv\\Scripts\\python.exe --version` -> `Access is denied`

### Impact

- Cannot run `python -m pip install -e .[dev]`.
- Cannot run `python -m pytest`.
- Runtime verification is blocked; only static code evidence can be collected.

### Mitigation Options

- Ensure a runnable Python interpreter is on PATH (`python` or `py`).
- Confirm execution permission for `.venv\\Scripts\\python.exe` in the workspace.
- If policy restricts local interpreter execution, run tests in an approved CI/runtime environment and link results in docs.

### Documentation Rule While Blocked

- Record exact command + error text in run logs.
- Do not claim runtime-passing status for blocked runs.
