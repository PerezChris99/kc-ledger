# Version control workflow

Only two branches are used: `main` is always deployable; `perez` is the sole development/integration branch. Never commit directly to main, never force-push main and do not create additional long-lived branches. Work on perez in small meaningful commits, with each commit compiling and passing the relevant smoke test.

At phase completion: run pytest, backend lint, frontend lint and production build; test the changed routes on desktop and mobile; review the diff for secrets and hardcoded UI colours; update the phase documentation; then merge perez to main with a merge commit, tag the phase and synchronise perez with main. Do not claim a phase is green until those checks actually pass.

Use Conventional Commits with a scoped imperative subject of at most 72 characters. The body explains why, and the footer references the phase when relevant. No CI workflows are configured; manual validation is mandatory.

## Changelog
- 2026-10-28: Reaffirmed the two-branch, no-CI workflow.
