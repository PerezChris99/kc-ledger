# Architecture

The browser hosts a React/Vite SPA. Nginx serves compiled assets and reverse-proxies /api/ and /admin/ to Django. Django Ninja exposes JSON endpoints; domain services contain deterministic financial logic; SQLite WAL persists records. TanStack Query is the server-data cache. The service worker will cache static app assets only.

Keep domain services separate from HTTP routers and ORM persistence. Mutations run transactionally and emit append-only audit events. Scoring consumes a snapshot and returns a result without database writes. Scheduled jobs must be idempotent and safe to rerun.

## Changelog
- 2026-10-28: Added initial architecture boundaries.
