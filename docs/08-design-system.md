# KC Ledger design system — current KC light-paper theme

The former **dark-first Terminal Ledger** appearance in the original master specification is historical; it was superseded by the KC brand redesign merged on 2026-11-01. The **implemented design** is a clean light-paper financial console.

| Token | Colour | Use |
| --- | --- | --- |
| `--kc-navy` | `#0B1B3D` | Brand, headings, sidebar |
| `--kc-cyan` | `#2CB4E8` | Highlight and interactive accent |
| `--kc-yellow` | `#F4C543` | Attention / warm brand accent |
| `--kc-gold` | `#D7A72A` | Premium accent |
| `--kc-paper` | `#F8F9FA` | Background |
| `--kc-white` | `#FFFFFF` | Raised panels |

Source of truth: [frontend/src/styles/globals.css](../frontend/src/styles/globals.css). The base body font size is 14px. Use consistent tokens for colour, spacing, type, borders and motion; avoid inline hardcoded palette overrides. Prefer restrained transitions and respect `prefers-reduced-motion`. Risk, warning, paid and overdue states should include text, not just colour.

**Acceptance conditions:** inspect dashboard, editing forms, tables, menus and dialogs at desktop and phone widths; test keyboard interaction, focus order, hover, reduced motion, zoom and colour contrast. Lint/build passing is not evidence that all of these were personally verified on physical devices.

_Updated 2026-11-15; supersedes the previous dark-first design document._
