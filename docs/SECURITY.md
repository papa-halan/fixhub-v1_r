# Security

## Current posture

This repository is still an MVP. The main security boundary improvements in the current code are:

- Passwords are stored as Argon2 hashes, not plaintext.
- Successful login can transparently upgrade legacy plaintext development rows to Argon2.
- Events and audit entries are appended inside the same transaction scope as the domain command.

## Development-only credentials

[`app/services/seed.py`](/C:/Users/halan/PycharmProjects/fixhub-v1/app/services/seed.py) creates fixed development users:

- `resident@uon.example`
- `staff@uon.example`
- `contractor@uon.example`
- `contractor-override@uon.example`

These credentials are for local development only. Do not reuse them outside a disposable development database.

## Password handling

Password helpers live in [`app/services/passwords.py`](/C:/Users/halan/PycharmProjects/fixhub-v1/app/services/passwords.py):

- `hash_password()` creates Argon2 hashes.
- `verify_and_upgrade_password_hash()` verifies current hashes and upgrades legacy plaintext rows on successful login.

The plaintext fallback exists only to migrate existing local seed data. New writes should always store Argon2 hashes.

## Remaining gaps

The repository still lacks several controls expected for production use:

- No rate limiting or account lockout.
- No MFA.
- No production-ready session or token management.
- No secret-management guidance beyond local environment variables.
- No CI pipeline yet enforcing dependency scanning or security checks.

Treat the current implementation as development-only until those controls exist.
