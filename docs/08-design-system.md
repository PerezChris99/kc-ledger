# Terminal Ledger design system

All UI colour, spacing, typography and border values are CSS custom properties in frontend/src/styles/globals.css. Components consume tokens; they do not introduce arbitrary hex values. Dark-first, compact and information-dense. Use blue for primary actions, green for positive outcomes, red for negative/destructive states and amber for warnings. Always pair colour with text or an icon. Financial figures, dates, percentages and identifiers use tabular monospaced numerals. Cards use a one-pixel border and 8px radius with no decorative shadow. Desktop uses a 12-column grid; mobile collapses to a usable single-column layout and bottom navigation.

## Changelog
- 2026-10-28: Established the initial token layer and responsive shell.
