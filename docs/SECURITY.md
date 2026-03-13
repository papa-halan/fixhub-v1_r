# Security

| Metadata | Value |
| --- | --- |
| Docs version | 0.2.0 |
| Status | Active |
| Owner | Security maintainer |
| Reviewers | Project maintainer; docs maintainer |
| Last updated | 2026-03-13 |
| Review cadence | On change and quarterly |

## Current State (Implemented)

This repository is an MVP and currently development-scoped.

Implemented controls:
- Password hashing via Argon2 (`app/services/passwords.py`).
- Legacy plaintext dev-row upgrade on successful login (`verify_and_upgrade_password_hash`).
- Domain events and audit entries appended in the same unit of work (`app/services/events.py`).
- Basic role/org scope checks in policy service (`app/services/policy.py`).

## Development Credentials

`app/services/seed.py` creates fixed development users:
- `resident@uon.example`
- `staff@uon.example`
- `contractor@uon.example`
- `contractor-override@uon.example`

These are local-development credentials only.

## Known Security Gaps (Current)

- No rate limiting or lockout policy.
- No MFA.
- No production-ready token/session strategy.
- No secret-management standard beyond local env vars.
- No enforced CI security gate in repository workflow.

## TODO (Proposed)

- TODO: Define production auth/session architecture (token type, expiry, revocation).
- TODO: Add security baseline checklist for releases.
- TODO: Add documented incident logging and audit review process.
- TODO: Add dependency and static security checks to CI as required gates.

## SD Practice Check and Feedback

Good:
- Current posture and limits are explicitly documented.
- Security caveats are clear for development-only usage.
- Security doc ownership and review cadence are now explicit.

Needs improvement:
- Missing threat model and risk ranking.
- No dedicated security-control verification process beyond normal document review.

## Change Log

- 2026-03-13 15:52:00 +11:00 (Australia/Sydney): Added owner/reviewer metadata and aligned the security doc with docs-set versioning.
- 2026-03-13 15:21:56 +11:00 (Australia/Sydney): Reworked security doc into implementation-backed controls, explicit gaps, and prioritized TODOs.
