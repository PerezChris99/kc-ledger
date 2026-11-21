# Instalment plan UX

The plan list shows each invoice's current verdict and its instalment schedule. The generator accepts an invoice with an outstanding balance, number of instalments, first due date, interval and grace days. It distributes cents evenly and assigns any remainder to the final instalment so the schedule equals the invoice balance exactly. The API validates positive amounts, unique sequence numbers, grace-day limits and the total balance in a transaction.

A plan starts In progress or At risk based on the due dates. Payment events recalculate its verdict, update plan metadata, emit a transition event and refresh the client score. Existing schedules are not silently overwritten.

## Changelog
- 2026-10-28: Added plan generation UI and transactional API.
