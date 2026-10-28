# Backlog and release gates

Items not yet fully verified or completed:

- Obtain five licensed real stock photographs, self-host them in the landing hero and implement the specified eight-second crossfade/pause/reduced-motion behaviour. The current entry screen uses CSS patterns instead.
- Verify a valid exchangerate.host account/key and confirm provider response shape; test FX refresh against the external service.
- Complete full client and invoice edit UX, instalment plan editing, engagement/time-entry/expense CRUD and target update/archive actions.
- Complete the remaining dashboard visual polish and confirm all content fits at 1440×900 and works at 375×667 on real browser builds.
- Add complete accessibility and keyboard/focus audits for every modal, popover and table.
- Add restore-drill instructions and verify backup restoration against a disposable database.
- Run the full Python test suite, Ruff, npm lint and production build in an environment with dependencies installed. No runtime build/test has yet been confirmed by the repository tool session.
- Review migrations with `makemigrations --check` and `migrate --plan`; test upgrade from a clean database and a copy of an existing database.
- Finish the remaining detailed feature documentation and produce diagrams in the preferred editable source format.

## Changelog
- 2026-10-28: Recorded known implementation and verification gaps.
