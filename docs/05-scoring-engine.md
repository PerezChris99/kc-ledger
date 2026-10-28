# Scoring engine

compute_client_score accepts a serializable snapshot and returns a deterministic score, eight factor explanations, penalties and a tier. It has no ORM writes. The factor maxima are payment speed 16, on-time rate 16, outstanding risk 10, revenue value 12, loyalty/repeat 8, relationship signals 12, rate health 10 and instalment discipline 16. Penalties are applied after factors: six per disputed invoice, up to 40 for write-off ratio, 14 per chargeback and 12 per abusive event. Blacklisted status forces score zero.

Each factor contains key, label, maximum, points, detail and verdict. Verify formula behaviour with unit tests whenever changing the weights or inputs.

## Changelog
- 2026-10-28: Added deterministic score service and initial tests.
