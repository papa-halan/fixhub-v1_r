from __future__ import annotations

import os
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
DOC_FILES = (
    ROOT / "README.md",
    ROOT / "docs" / "README.md",
    ROOT / "docs" / "CHANGELOG.md",
    ROOT / "docs" / "schema_student_living_assessment.md",
)
CODE_PATHS = (
    ROOT / "app" / "models",
    ROOT / "app" / "api",
    ROOT / "app" / "schema",
    ROOT / "app" / "services",
    ROOT / "alembic" / "versions",
)


def _latest_mtime(paths: tuple[Path, ...]) -> float:
    latest = 0.0
    for path in paths:
        if path.is_file():
            latest = max(latest, path.stat().st_mtime)
            continue
        if not path.exists():
            continue
        for child in path.rglob("*"):
            if child.is_file() and ".venv" not in child.parts and ".git" not in child.parts:
                latest = max(latest, child.stat().st_mtime)
    return latest


def test_docs_are_updated_with_code_surface_changes() -> None:
    if os.getenv("FIXHUB_DOCS_FRESHNESS_BYPASS") == "1":
        pytest.skip("docs freshness gate bypassed with FIXHUB_DOCS_FRESHNESS_BYPASS=1")

    latest_code_change = _latest_mtime(CODE_PATHS)
    latest_docs_change = _latest_mtime(DOC_FILES)

    assert latest_docs_change >= latest_code_change, (
        "Documentation is older than code/schema changes. "
        "Update README diagrams and docs/ changelog/assessment for this run "
        "or set FIXHUB_DOCS_FRESHNESS_BYPASS=1 for intentional exceptions."
    )
