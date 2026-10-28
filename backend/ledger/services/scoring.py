from dataclasses import asdict, dataclass
from datetime import date
from math import log1p
from typing import Any, Mapping

from .instalments import VERDICT_WEIGHTS


@dataclass(frozen=True)
class Factor:
    key: str
    label: str
    maximum: int
    points: float
    detail: str
    verdict: str


@dataclass(frozen=True)
class ScoreResult:
    score: int
    tier: str
    factors: tuple[Factor, ...]
    penalties: tuple[dict[str, Any], ...]

    def as_dict(self) -> dict[str, Any]:
        return {"score": self.score, "tier": self.tier,
                "factors": [asdict(item) for item in self.factors],
                "penalties": list(self.penalties)}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _money(value: Any) -> float:
    try:
        return max(0.0, float(value or 0))
    except (TypeError, ValueError):
        return 0.0


def _date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def compute_client_score(snapshot: Mapping[str, Any], as_of: date | None = None) -> ScoreResult:
    """Pure, deterministic 8-factor client score. Input is a serializable domain snapshot."""
    today = as_of or date.today()
    invoices = list(snapshot.get("invoices", []))
    settled = [i for i in invoices if i.get("status") == "paid" or i.get("paid_on")]
    billed = sum(_money(i.get("amount")) for i in invoices if i.get("status") != "written_off")
    overdue = sum(_money(i.get("outstanding", i.get("amount", 0))) for i in invoices
                   if i.get("status") not in {"paid", "written_off", "disputed"}
                   and (_date(i.get("due_date")) or today) < today)
    total_collected = _money(snapshot.get("lifetime_collected", sum(_money(i.get("collected")) for i in invoices)))
    best_collected = max(total_collected, _money(snapshot.get("best_client_collected", total_collected)), 1.0)

    late_weight = 0.0
    settled_weight = 0.0
    on_time_amount = 0.0
    settled_amount = 0.0
    for invoice in settled:
        amount = _money(invoice.get("amount"))
        due = _date(invoice.get("due_date"))
        paid = _date(invoice.get("paid_on"))
        if due and paid:
            days_late = max(0, (paid - due).days)
            late_weight += amount * days_late
            settled_weight += amount
            settled_amount += amount
            if days_late == 0:
                on_time_amount += amount
    average_late = late_weight / settled_weight if settled_weight else 0.0
    payment_speed = 16.0 * _clamp(1.0 - average_late / 60.0, 0.0, 1.0) if settled_weight else 8.0
    on_time_rate = on_time_amount / settled_amount if settled_amount else 0.5
    on_time = 16.0 * on_time_rate
    outstanding_risk = 10.0 * (1.0 - _clamp(overdue / billed, 0.0, 1.0)) if billed else 10.0
    revenue_value = 12.0 * log1p(total_collected) / log1p(best_collected) if total_collected else 0.0
    started = _date(snapshot.get("started_at"))
    tenure_years = max(0.0, (today - started).days / 365.25) if started else 0.0
    engagement_count = max(0, int(snapshot.get("engagement_count", 0)))
    loyalty = 8.0 * _clamp((tenure_years / 3.0) * 0.5 + (engagement_count / 6.0) * 0.5, 0.0, 1.0)

    events = list(snapshot.get("events", []))
    positive = sum(max(0.0, float(e.get("weight", 1))) for e in events if int(e.get("polarity", 0)) > 0)
    negative = sum(max(0.0, float(e.get("weight", 1))) for e in events if int(e.get("polarity", 0)) < 0)
    relationship = 12.0 * _clamp(0.5 + (positive - negative) / 20.0, 0.0, 1.0)
    increases = max(0, int(snapshot.get("accepted_rate_increases", 0)))
    haggling = max(0, int(snapshot.get("haggling_events", 0)))
    rate_health = 10.0 * _clamp(0.5 + (increases - haggling) / 10.0, 0.0, 1.0)
    verdicts = list(snapshot.get("plan_verdicts", []))
    plan_discipline = 16.0 * (sum(VERDICT_WEIGHTS.get(str(v).lower().replace(" ", "_"), 0.7) for v in verdicts) / len(verdicts)) if verdicts else 11.2

    factors = [
        Factor("payment_speed", "Payment speed", 16, round(payment_speed, 2), f"Amount-weighted average lateness: {average_late:.1f} days.", "good" if payment_speed >= 12 else "watch"),
        Factor("on_time_rate", "On-time rate", 16, round(on_time, 2), f"{on_time_rate:.0%} of settled invoice value was paid on time.", "good" if on_time >= 12 else "watch"),
        Factor("outstanding_risk", "Outstanding risk", 10, round(outstanding_risk, 2), f"{overdue:.2f} overdue against {billed:.2f} billed.", "good" if outstanding_risk >= 7 else "risk"),
        Factor("revenue_value", "Revenue value", 12, round(_clamp(revenue_value, 0, 12), 2), f"Lifetime collected: {total_collected:.2f}.", "good" if revenue_value >= 6 else "neutral"),
        Factor("loyalty_repeat", "Loyalty and repeat", 8, round(loyalty, 2), f"{tenure_years:.1f} years of tenure and {engagement_count} engagements.", "good" if loyalty >= 4 else "neutral"),
        Factor("relationship_signals", "Relationship signals", 12, round(relationship, 2), f"{positive:.1f} positive weight and {negative:.1f} negative weight.", "good" if relationship >= 8 else "watch"),
        Factor("rate_health", "Rate health", 10, round(rate_health, 2), f"{increases} accepted rate increases and {haggling} haggling events.", "good" if rate_health >= 6 else "watch"),
        Factor("instalment_discipline", "Instalment discipline", 16, round(plan_discipline, 2), f"Based on {len(verdicts)} plan verdicts.", "good" if plan_discipline >= 11 else "risk"),
    ]
    penalties = []
    disputed = sum(1 for i in invoices if i.get("status") == "disputed")
    writeoff = sum(_money(i.get("amount")) for i in invoices if i.get("status") == "written_off")
    total_invoiced = sum(_money(i.get("amount")) for i in invoices)
    chargebacks = max(0, int(snapshot.get("chargebacks", 0)))
    abusive = sum(1 for e in events if e.get("kind") == "abusive")
    for key, label, amount in [
        ("disputed_invoices", "Disputed invoices", min(1000, disputed * 6)),
        ("writeoff_ratio", "Write-off ratio", min(40, 40 * writeoff / total_invoiced if total_invoiced else 0)),
        ("chargebacks", "Chargebacks", min(1000, chargebacks * 14)),
        ("abusive_events", "Abusive events", min(1000, abusive * 12)),
    ]:
        if amount:
            penalties.append({"key": key, "label": label, "points": round(amount, 2)})
    total_penalty = sum(float(item["points"]) for item in penalties)
    raw = sum(f.points for f in factors) - total_penalty
    score = 0 if snapshot.get("status") == "blacklisted" else int(round(_clamp(raw, 0, 100)))
    tier = "Champion" if score >= 85 else "Reliable" if score >= 70 else "Neutral" if score >= 55 else "Caution" if score >= 40 else "Avoid"
    return ScoreResult(score, tier, tuple(factors), tuple(penalties))
