# Instalment allocation and verdict engine

Payments are allocated FIFO across scheduled instalments, ordered by due date and sequence, respecting prior allocations and the remaining amount of each row. The allocator returns explicit allocations and any unallocated remainder. The API rejects payment amounts above the invoice's outstanding balance and records payment plus allocations in a transaction.

Plan verdicts are Perfect, Late, In progress, At risk and Broken. Due dates, grace periods, payment dates and the length of overdue periods determine the verdict. A scheduled job advances pending instalments to overdue or missed and emits an event when a saved verdict changes. The client score consumes the plan verdict ratio.

## Changelog
- 2026-10-28: Added FIFO allocation, verdict evaluation and edge-case tests.
