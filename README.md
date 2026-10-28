# KC Ledger

Private financial operations console for a solo freelance developer.

KC Ledger tracks client profitability, invoices, payments, instalment plans, explainable client health scores, cash flow, and an append-only audit trail.

## Canonical specification

The master product and engineering specification is maintained at [`docs/00-master-spec.md`](docs/00-master-spec.md). Implementation follows its locked Django 5 + Django Ninja + SQLite WAL backend and React 18 + TypeScript + Vite frontend architecture.

## Development workflow

- `main` is the production-ready branch.
- `perez` is the only implementation branch.
- No CI workflows.
- Each phase must be tested, documented, merged to `main`, and tagged before proceeding.

## Status

Bootstrap is being established. Features are not considered complete until implemented and verified.