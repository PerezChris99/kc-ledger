# Instalment engine

Payment allocation is FIFO by due date, then sequence, and only covers the unpaid balance of non-paid, non-waived instalments. Partial allocations are supported. Excess payment is returned as unallocated for explicit handling rather than silently lost.

Plan verdicts are Perfect, Late, In progress, At risk and Broken. Fully settled plans are Perfect unless an instalment was paid after its due date plus grace, in which case the plan is Late. Unpaid instalments due within three days or beyond grace are At risk; an unpaid instalment more than thirty days beyond grace is Broken. Empty and not-yet-due plans are In progress.

## Changelog
- 2026-10-28: Added FIFO allocator and five-verdict evaluator.
