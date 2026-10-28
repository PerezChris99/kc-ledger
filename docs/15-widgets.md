# Persistent widgets

The application shell contains a live clock, calendar popover, FX converter and target tracker. The clock reads the saved display timezone. Calendar dates come from invoice and instalment records. The converter uses stored direct or inverse FX rates and explains when a pair is unavailable. Targets are stored in the database and revenue/client/hour progress uses server totals; currency conversion is only possible where a matching FX rate exists.

## Changelog
- 2026-10-28: Added clock, calendar, FX conversion and target persistence.
