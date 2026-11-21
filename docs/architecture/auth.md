# Authentication

KC Ledger uses Django session authentication. Private API endpoints require an active staff account; unsafe requests require CSRF protection. The login endpoint accepts credentials over the same origin and does not disclose whether a username exists. Session cookies are HttpOnly and SameSite=Lax. Set COOKIE_SECURE=1 when HTTPS terminates in front of Django.

On first startup, ensure_owner creates the initial staff superuser only when LEDGER_USERNAME and a unique LEDGER_PASSWORD of at least 16 characters are configured. In production, DJANGO_SECRET_KEY must be a random value of at least 40 characters. Existing owner passwords are never reset automatically. Never use the example environment values in production.

## Changelog
- 2026-10-28: Added initial staff-only session authentication and bootstrap credential checks.
