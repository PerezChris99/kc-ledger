# Client health scoring engine

The scoring engine computes an explainable integer from 0–100. It is a pure service: it receives a snapshot and reference date, performs no ORM writes and returns the total, tier, factor-by-factor explanation and explicit penalties. API handlers persist the cached score separately.

## Weighted factors

| Factor | Maximum |
|---|---:|
| Payment speed | 16 |
| On-time rate | 16 |
| Outstanding risk | 10 |
| Revenue value | 12 |
| Loyalty and repeat business | 8 |
| Relationship signals | 12 |
| Rate health | 10 |
| Instalment discipline | 16 |
| **Total before penalties** | **100** |

Penalties are applied after the factors: 6 points per disputed invoice, up to 40 points based on write-off ratio, 14 per chargeback and 12 per abusive event. A blacklisted client receives zero. Plan verdict ratios are Perfect 1.0, Late 0.5, In progress 0.7, At risk 0.2 and Broken 0.0.

## Tiers

Champion 85–100; Reliable 70–84; Neutral 55–69; Caution 40–54; Avoid 0–39. Each factor exposes `key`, `label`, `maximum`, `points`, `detail` and `verdict` so the UI can explain its result.

## Changelog
- 2026-10-28: Implemented the pure scoring service and factor tests.
