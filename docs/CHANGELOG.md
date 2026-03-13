# Documentation Changelog

| Metadata | Value |
| --- | --- |
| Docs version | 0.2.0 |
| Status | Active |
| Owner | Docs maintainer |
| Reviewers | Project maintainer; docs maintainer |
| Last updated | 2026-03-13 |
| Review cadence | On change and quarterly |

This file tracks changes to the maintained documentation set in `README.md` and `docs/`.

## Versioning Rules

- Major: structural reset or docs policy change across the maintained documentation set.
- Minor: new maintained documents, ADRs, or notable process additions.
- Patch: factual corrections, link fixes, or implementation-sync updates.

## [0.2.0] - 2026-03-13

Added:
- ADR history for core model choices in [`docs/adr/`](adr/README.md).
- Owner/reviewer metadata and review cadence across the maintained docs set.
- Versioned documentation changelog tracking.

Changed:
- Root README and docs index now reference ADR and changelog artifacts.
- Schema assessment links now use repository-relative paths for portability.

## [0.1.0] - 2026-03-13

Added:
- Docs index in [`docs/README.md`](README.md).
- Structured current-state, TODO, and SD-practice sections across the docs set.

Changed:
- Root README and `docs/*.md` were refactored to separate implemented behavior from proposed improvements.
