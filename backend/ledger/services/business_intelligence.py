"""Explainable business-wide ledger intelligence; deterministic, offline and auditable.

These calculations report RECORDED cash receipts less RECORDED expenses, not
GAAP/IFRS profit, actual bank balances or full business cash flow. Forecasts are
illustrative, never guaranteed, and no model is allowed to write source data.
"""

from collections import Counter, defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from statistics import median

from django.utils import timezone

from ledger.models import (
    BusinessObjective,
    BusinessStrategyDecision,
    Client,
    Engagement,
    Expense,
    Invoice,
    Payment,
    TimeEntry,
)
from ledger.services.fx import conversion_for

ZERO = Decimal(0)
ONE = Decimal(1)
CENT = Decimal("0.01")
METRIC_MAXIMIZE = {
    BusinessObjective.Metric.MONTHLY_RECEIPTS,
    BusinessObjective.Metric.MONTHLY_CASH_RESULT,
    BusinessObjective.Metric.ACTIVE_CLIENTS,
    BusinessObjective.Metric.CASH_PER_HOUR,
}
METRIC_MINIMIZE = {
    BusinessObjective.Metric.MONTHLY_EXPENSES,
    BusinessObjective.Metric.OVERDUE_BALANCE,
}


def amount(value):
    return str(Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP))


def _shift_month(day, offset):
    month_index = day.year * 12 + day.month - 1 + offset
    return date(month_index // 12, month_index % 12 + 1, 1)


def _month(day):
    return day.strftime("%Y-%m")


def _rule(key, level, title, evidence, action, avoid, confidence="observed"):
    return {
        "id": key,
        "priority": level,
        "title": title,
        "evidence": evidence,
        "action": action,
        "avoid": avoid,
        "confidence": confidence,
        "source": "Recorded ledger facts and deterministic thresholds",
    }


def _median(rows):
    return median(rows) if rows else ZERO


def _rough_forecast(monthly):
    # Exclude the partial current month from the baseline; use the last 6 complete.
    past = monthly[-7:-1]
    active = [m for m in past if m["receipt_count"] or m["expense_count"]]
    if len(active) < 3:
        return {
            "available": False,
            "confidence": "insufficient",
            "reason": "At least three completed months with recorded financial activity are required.",
            "sample_months": len(active),
        }
    receipts = [Decimal(m["receipts"]) for m in past]
    costs = [Decimal(m["expenses"]) for m in past]
    r, c = _median(receipts), _median(costs)
    spread_receipts = max(_median([abs(value - r) for value in receipts]), r * Decimal("0.25"))
    spread_costs = max(_median([abs(value - c) for value in costs]), c * Decimal("0.25"))
    low = max(ZERO, r - spread_receipts) - (c + spread_costs)
    high = r + spread_receipts - max(ZERO, c - spread_costs)
    return {
        "available": True,
        "confidence": "low",
        "sample_months": len(active),
        "period": "next full calendar month",
        "receipts_baseline": amount(r),
        "expenses_baseline": amount(c),
        "cash_result_baseline": amount(r - c),
        "illustrative_low": amount(low),
        "illustrative_high": amount(high),
        "method": "Median of six completed months; MAD or 25% baseline variability.",
        "warning": (
            "A scenario from past recorded cash activity, not a prediction interval, "
            "profit forecast, promise of payment, or bank balance. "
            "Seasonality and unrecorded costs are not modeled."
        ),
    }


def _monthly_anomalies(monthly):
    closed = monthly[:-1]
    if len(closed) < 4:
        return []
    latest = closed[-1]
    previous = closed[-4:-1]
    rows = []
    for metric, label in (
        ("receipts", "Cash receipts"),
        ("expenses", "Recorded expenses"),
    ):
        past = [Decimal(row[metric]) for row in previous]
        if sum(1 for row in previous if row["receipt_count"] or row["expense_count"]) < 3:
            continue
        baseline = _median(past)
        last = Decimal(latest[metric])
        if baseline <= ZERO:
            continue
        mad = _median([abs(x - baseline) for x in past])
        distance = last - baseline
        threshold = max(baseline * Decimal("0.30"), mad * 3)
        if abs(distance) <= threshold:
            continue
        adverse = (metric == "receipts" and distance < 0) or (metric == "expenses" and distance > 0)
        rows.append(
            {
                "id": metric + "_deviation",
                "metric": metric,
                "month": latest["month"],
                "direction": "increase" if distance > 0 else "decrease",
                "severity": "warning" if adverse else "informational",
                "last_value": amount(last),
                "median_previous_three": amount(baseline),
                "change_pct": round(float(distance / baseline * 100), 1),
                "description": (
                    f"{label} changed materially versus the previous three completed months."
                ),
                "caution": (
                    "An unusual change is not proof of fraud, causation, or a future trend."
                ),
            }
        )
    return rows


def build_business_snapshot(as_of=None, base=None):
    """One FX lookup and bounded aggregation passes for all primary evidence."""
    today = as_of or timezone.localdate()
    if base is None:
        from ledger.api_extra import _get_app_settings

        base = _get_app_settings()["base_currency"]
    convert = conversion_for(base)
    months = [_shift_month(today, offset) for offset in range(-12, 1)]
    monthly = {
        _month(day): {
            "month": _month(day),
            "receipts": ZERO,
            "expenses": ZERO,
            "receipt_count": 0,
            "expense_count": 0,
        }
        for day in months
    }
    collected = expenses = overdue = outstanding = billed = written_off = ZERO
    unpaid_disputed = ZERO
    incomplete_fx = set()
    client_receipts = defaultdict(lambda: ZERO)
    client_expenses = defaultdict(lambda: ZERO)
    client_hours = defaultdict(lambda: ZERO)
    client_overdue = defaultdict(lambda: ZERO)
    category_costs = defaultdict(lambda: ZERO)
    engagement_hours = defaultdict(lambda: ZERO)
    revenue_by_engagement = defaultdict(lambda: ZERO)
    expenses_by_engagement = defaultdict(lambda: ZERO)
    outstanding_aging = defaultdict(lambda: ZERO)
    paid_by_invoice = defaultdict(lambda: ZERO)
    invoice_status = Counter()
    receipts_count = expenses_count = 0

    for payment in (
        Payment.objects.select_related("invoice", "client").all().iterator(chunk_size=400)
    ):
        paid_by_invoice[payment.invoice_id] += payment.amount
        value = convert(payment.amount, payment.invoice.currency)
        if value is None:
            incomplete_fx.add(payment.invoice.currency)
            continue
        collected += value
        receipts_count += 1
        client_receipts[payment.client_id] += value
        if payment.invoice.engagement_id:
            revenue_by_engagement[payment.invoice.engagement_id] += value
        month = monthly.get(_month(payment.paid_on))
        if month:
            month["receipts"] += value
            month["receipt_count"] += 1

    for entry in Expense.objects.all().iterator(chunk_size=400):
        value = convert(entry.amount, entry.currency)
        if value is None:
            incomplete_fx.add(entry.currency)
            continue
        expenses += value
        expenses_count += 1
        category_costs[entry.category.strip() or "Uncategorized"] += value
        if entry.client_id:
            client_expenses[entry.client_id] += value
        if entry.engagement_id:
            expenses_by_engagement[entry.engagement_id] += value
        month = monthly.get(_month(entry.spent_on))
        if month:
            month["expenses"] += value
            month["expense_count"] += 1

    for row in (
        TimeEntry.objects.all()
        .values("client_id", "engagement_id", "hours", "category")
        .iterator(chunk_size=400)
    ):
        client_hours[row["client_id"]] += row["hours"]
        engagement_hours[row["engagement_id"]] += row["hours"]

    inconsistent_invoice_count = 0
    for invoice in Invoice.objects.all().iterator(chunk_size=400):
        invoice_status[invoice.status] += 1
        paid = paid_by_invoice[invoice.id]
        if paid > invoice.amount or (
            invoice.status == Invoice.Status.PAID and paid < invoice.amount
        ):
            inconsistent_invoice_count += 1
        full = convert(invoice.amount, invoice.currency)
        balance = convert(max(ZERO, invoice.amount - paid), invoice.currency)
        if full is None or balance is None:
            incomplete_fx.add(invoice.currency)
            continue
        if invoice.status != Invoice.Status.DRAFT:
            billed += full
        if invoice.status == Invoice.Status.WRITTEN_OFF:
            written_off += balance
            continue
        if invoice.status != Invoice.Status.DRAFT:
            outstanding += balance
            if invoice.status == Invoice.Status.DISPUTED:
                unpaid_disputed += balance
            if balance > ZERO:
                age = (today - invoice.due_date).days
                aging = (
                    "not_due"
                    if age <= 0
                    else "1_30"
                    if age <= 30
                    else "31_60"
                    if age <= 60
                    else "61_plus"
                )
                outstanding_aging[aging] += balance
                if age > 0:
                    overdue += balance
                    client_overdue[invoice.client_id] += balance

    clients = list(Client.objects.values("id", "name", "status", "score"))
    active_clients = sum(row["status"] == Client.Status.ACTIVE for row in clients)
    total_hours = sum(client_hours.values(), ZERO)
    monthly_rows = [
        {
            "month": row["month"],
            "receipts": amount(row["receipts"]),
            "expenses": amount(row["expenses"]),
            "cash_result": amount(row["receipts"] - row["expenses"]),
            "receipt_count": row["receipt_count"],
            "expense_count": row["expense_count"],
            "complete": row["month"] != _month(today),
        }
        for row in monthly.values()
    ]
    cash_result = collected - expenses
    latest_complete = monthly_rows[-2]
    cash_per_hour = collected / total_hours if total_hours else None

    contributions = []
    for item in clients:
        cid = item["id"]
        rec, costs = client_receipts[cid], client_expenses[cid]
        contributions.append(
            {
                "id": cid,
                "client": item["name"],
                "status": item["status"],
                "score": item["score"],
                "receipts": amount(rec),
                "direct_expenses": amount(costs),
                "direct_cash_contribution": amount(rec - costs),
                "outstanding_overdue": amount(client_overdue[cid]),
                "logged_hours": amount(client_hours[cid]),
                "cash_per_hour": amount(rec / client_hours[cid]) if client_hours[cid] else None,
            }
        )
    contributions.sort(key=lambda row: Decimal(row["receipts"]), reverse=True)
    top_share = (
        Decimal(contributions[0]["receipts"]) / collected if contributions and collected else ZERO
    )
    project_rows = []
    for eng in Engagement.objects.select_related("client").all():
        hours = engagement_hours[eng.id]
        received = revenue_by_engagement[eng.id]
        direct_costs = expenses_by_engagement[eng.id]
        project_rows.append(
            {
                "id": eng.id,
                "engagement": eng.name,
                "client": eng.client.name,
                "kind": eng.kind,
                "status": eng.status,
                "received": amount(received),
                "direct_costs": amount(direct_costs),
                "direct_cash_contribution": amount(received - direct_costs),
                "logged_hours": amount(hours),
            }
        )
    project_rows.sort(key=lambda row: Decimal(row["received"]), reverse=True)
    anomaly_rows = _monthly_anomalies(monthly_rows)
    forecast = _rough_forecast(monthly_rows)
    metrics = {
        BusinessObjective.Metric.MONTHLY_RECEIPTS: Decimal(latest_complete["receipts"]),
        BusinessObjective.Metric.MONTHLY_CASH_RESULT: Decimal(latest_complete["cash_result"]),
        BusinessObjective.Metric.MONTHLY_EXPENSES: Decimal(latest_complete["expenses"]),
        BusinessObjective.Metric.OVERDUE_BALANCE: overdue,
        BusinessObjective.Metric.ACTIVE_CLIENTS: Decimal(active_clients),
        BusinessObjective.Metric.CASH_PER_HOUR: cash_per_hour,
    }
    rules = []
    if receipts_count + expenses_count == 0:
        rules.append(
            _rule(
                "unmeasured_cash",
                "high",
                "Business cash performance is not measurable yet",
                "No recorded payment or expense entries can be converted.",
                "Record all receipts and costs before drawing financial conclusions.",
                "Do not conclude that zero expenses means the business is profitable.",
                "insufficient",
            )
        )
    if incomplete_fx:
        rules.append(
            _rule(
                "fx_gaps",
                "high",
                "Financial totals are incomplete",
                f"Missing conversion rates: {', '.join(sorted(incomplete_fx))}.",
                "Configure verified currency conversion pairs and recalculate before decisions.",
                "Do not compare mixed currencies or treat excluded amounts as zero.",
            )
        )
    if inconsistent_invoice_count:
        rules.append(
            _rule(
                "invoice_integrity",
                "high",
                "Invoice settlement inconsistencies require review",
                f"{inconsistent_invoice_count} paid-status / amount mismatch(es).",
                "Reconcile individual invoices and payment allocations against source records.",
                "Do not base collection strategy on unreconciled settlements.",
            )
        )
    if cash_result < ZERO and receipts_count + expenses_count:
        rules.append(
            _rule(
                "negative_cash",
                "high",
                "Recorded outflows exceed receipts",
                f"Recorded receipts {amount(collected)} less recorded expenses {amount(expenses)} = {amount(cash_result)} {base}.",
                "Inspect largest cost categories, speed up legitimate collections and protect cash commitments.",
                "Do not assume revenue bookings or unpaid invoices cover outgoing cash.",
            )
        )
    if outstanding > ZERO and overdue / outstanding >= Decimal("0.3"):
        rules.append(
            _rule(
                "overdue_exposure",
                "high",
                "A large share of unpaid invoices is overdue",
                f"{amount(overdue)} {base} overdue out of {amount(outstanding)} {base} unpaid.",
                "Segment overdue invoices by age, contact payers, and ask for dated settlement plans.",
                "Do not continue unsecured work without reviewing payment exposure.",
            )
        )
    if len(
        [row for row in contributions if Decimal(row["receipts"]) > ZERO]
    ) >= 2 and top_share > Decimal("0.45"):
        rules.append(
            _rule(
                "revenue_concentration",
                "medium",
                "Cash receipts depend heavily on one client",
                f"Top client's share of recorded receipts is {float(top_share * 100):.1f}%.",
                "Develop additional qualified clients and retain clear agreements with major accounts.",
                "Do not assume the largest current payer guarantees future income.",
            )
        )
    if expenses and collected and expenses / collected >= Decimal("0.8"):
        rules.append(
            _rule(
                "cash_cost_pressure",
                "medium",
                "Expenses absorb most recorded receipts",
                f"Recorded costs equal {float(expenses / collected * 100):.1f}% of receipts.",
                "Break down spending by category; review low-return work and unavoidable overhead.",
                "Do not cut essential delivery capacity without evaluating service impact.",
            )
        )
    for anomaly in anomaly_rows:
        if anomaly["severity"] == "warning":
            rules.append(
                _rule(
                    "anomaly_" + anomaly["id"],
                    "medium",
                    anomaly["description"],
                    f"{anomaly['month']}: {anomaly['metric']} changed {anomaly['change_pct']}% from the three-month median.",
                    "Investigate source transactions and one-off effects before adapting the plan.",
                    "Do not extrapolate a single unusual month into a guaranteed trend.",
                    "limited",
                )
            )
    if receipts_count and not expenses_count:
        rules.append(
            _rule(
                "cost_coverage",
                "high",
                "Expenses may be missing",
                "Recorded receipts exist, but no expense entries are present.",
                "Capture vendor bills, software subscriptions, taxes and other real costs.",
                "Do not present collected cash as net profit.",
                "insufficient",
            )
        )
    if active_clients and receipts_count:
        low_clients = [
            row
            for row in contributions
            if row["status"] == Client.Status.ACTIVE
            and Decimal(row["direct_cash_contribution"]) < ZERO
        ]
        if low_clients:
            rules.append(
                _rule(
                    "negative_client_cash",
                    "medium",
                    "Some clients have negative direct cash contribution",
                    f"{len(low_clients)} active client(s) have more allocated expenses than receipts.",
                    "Review their pricing, delivery scope, payment terms and whether costs were allocated correctly.",
                    "Do not call this accounting loss without allocating labor and shared overhead.",
                )
            )
    rules.sort(key=lambda x: ({"high": 0, "medium": 1, "low": 2}[x["priority"]], x["id"]))
    return {
        "as_of": today.isoformat(),
        "currency": base,
        "metrics": {
            "collected": amount(collected),
            "expenses": amount(expenses),
            "recorded_net_cash": amount(cash_result),
            "outstanding": amount(outstanding),
            "overdue": amount(overdue),
            "billed_non_draft": amount(billed),
            "written_off": amount(written_off),
            "unpaid_disputed": amount(unpaid_disputed),
            "active_clients": active_clients,
            "client_count": len(clients),
            "receipt_count": receipts_count,
            "expense_count": expenses_count,
            "logged_hours": amount(total_hours),
            "cash_per_logged_hour": amount(cash_per_hour) if cash_per_hour else None,
            "top_client_share_pct": round(float(top_share * 100), 1),
            "unassigned_expenses": amount(expenses - sum(client_expenses.values(), ZERO)),
        },
        "metric_values": metrics,
        "monthly": monthly_rows,
        "client_contribution": contributions[:100],
        "expense_categories": [
            {"category": cat, "amount": amount(value)}
            for cat, value in sorted(category_costs.items(), key=lambda item: (-item[1], item[0]))[
                :25
            ]
        ],
        "projects": project_rows[:100],
        "aging": [
            {"bucket": name, "amount": amount(outstanding_aging[name])}
            for name in ("not_due", "1_30", "31_60", "61_plus")
        ],
        "invoice_status": [
            {"name": key, "count": value} for key, value in sorted(invoice_status.items())
        ],
        "forecast": forecast,
        "anomalies": anomaly_rows,
        "recommendations": rules,
        "data_quality": {
            "missing_fx": sorted(incomplete_fx),
            "invoice_mismatches": inconsistent_invoice_count,
            "expense_capture_verified": False,
            "unrecorded_costs_possible": True,
            "classification": "recorded cash movement, not audited accounting profit",
            "notes": [
                "Receipts reflect recorded payments and expenses reflect recorded cost entries.",
                "Accrual income, taxes, owner pay, depreciation, liabilities and complete cost allocations are not verified.",
                "Cash result is not bank balance or accounting profit/loss.",
                "FX conversions use the currently stored rates, not historical transaction rates.",
                "Per-client direct contribution excludes unallocated/shared costs and unrecorded labor.",
            ],
        },
    }


def objective_progress(objective, snapshot):
    current = snapshot["metric_values"].get(objective.metric)
    max_direction = objective.metric in METRIC_MAXIMIZE
    metric_is_currency = objective.metric != BusinessObjective.Metric.ACTIVE_CLIENTS
    available = current is not None and (
        not snapshot["data_quality"]["missing_fx"] or not metric_is_currency
    )
    target = objective.target
    favorable = (current >= target if max_direction else current <= target) if available else None
    delta = current - target if available else None
    return {
        "id": objective.id,
        "name": objective.name,
        "description": objective.description,
        "metric": objective.metric,
        "target": amount(target),
        "current": amount(current) if available else None,
        "variance": amount(delta) if available else None,
        "favorable": favorable,
        "direction": "increase" if max_direction else "decrease",
        "status": objective.status,
        "due_date": objective.due_date.isoformat(),
        "days_remaining": (objective.due_date - date.fromisoformat(snapshot["as_of"])).days,
        "metric_context": (
            "Last completed calendar month"
            if objective.metric.startswith("monthly_")
            else "Live ledger total"
            if objective.metric != BusinessObjective.Metric.CASH_PER_HOUR
            else "All recorded receipts / all logged hours"
        ),
        "caution": "A current observation is not evidence that a strategy caused a change.",
    }


def decision_review(decision, snapshot):
    current = snapshot["metric_values"].get(decision.metric)
    available = current is not None and (
        not snapshot["data_quality"]["missing_fx"] or decision.metric == "active_clients"
    )
    delta = current - decision.baseline if available and decision.baseline is not None else None
    favorable = (
        (delta >= ZERO if decision.metric in METRIC_MAXIMIZE else delta <= ZERO)
        if delta is not None
        else None
    )
    return {
        "id": decision.id,
        "title": decision.title,
        "kind": decision.kind,
        "rationale": decision.rationale,
        "expected_effect": decision.expected_effect,
        "client_id": decision.client_id,
        "client_name": decision.client.name if decision.client else None,
        "objective_id": decision.objective_id,
        "metric": decision.metric,
        "baseline": amount(decision.baseline) if decision.baseline is not None else None,
        "current": amount(current) if available else None,
        "observed_change": amount(delta) if delta is not None else None,
        "direction_favorable": favorable,
        "status": decision.status,
        "started_on": decision.started_on.isoformat(),
        "review_on": decision.review_on.isoformat(),
        "review_due": decision.review_on <= date.fromisoformat(snapshot["as_of"])
        and decision.status
        in {BusinessStrategyDecision.Status.ACTIVE, BusinessStrategyDecision.Status.PLANNED},
        "outcome_note": decision.outcome_note,
        "caution": "Before/after association, not a causal estimate; review confounders and incomplete data.",
    }


def prioritize_goals_and_decisions(snapshot, objectives, decisions):
    recommendations = list(snapshot["recommendations"])
    for goal in objectives:
        if goal.status != BusinessObjective.Status.ACTIVE:
            continue
        row = objective_progress(goal, snapshot)
        if row["favorable"] is False and row["days_remaining"] <= 30:
            recommendations.append(
                _rule(
                    "goal_" + str(goal.id),
                    "medium" if row["days_remaining"] > 0 else "high",
                    "Your stated target is not yet met: " + goal.name,
                    f"{goal.metric}: current {row['current']}, target {row['target']}, due {row['due_date']}.",
                    "Compare controllable activities against the stated target; change or scale down weak tactics.",
                    "Do not declare a strategy successful just because it was executed.",
                    "limited",
                )
            )
    for decision in decisions:
        row = decision_review(decision, snapshot)
        if row["review_due"]:
            recommendations.append(
                _rule(
                    "decision_" + str(decision.id),
                    "medium",
                    "Review your previous strategic decision: " + decision.title,
                    f"Recorded baseline {row['baseline'] or 'unknown'}; current {row['current'] or 'unknown'}.",
                    "Document the observed result, external factors, and whether to keep, adjust or stop the tactic.",
                    "Do not claim the action caused an increase or decrease without stronger evidence.",
                    "limited",
                )
            )
        elif (
            decision.status == BusinessStrategyDecision.Status.REVIEWED
            and row["direction_favorable"] is False
        ):
            recommendations.append(
                _rule(
                    "decision_correct_" + str(decision.id),
                    "medium",
                    "The metric moved against the intention of a past decision",
                    f"{decision.title}: observed change {row['observed_change']} against a recorded baseline.",
                    "Check whether assumptions failed, and consider revising the pricing or delivery approach.",
                    "Do not repeat an underperforming tactic uncritically or assign causation from correlation.",
                    "limited",
                )
            )
    return sorted(
        recommendations,
        key=lambda x: ({"high": 0, "medium": 1, "low": 2}[x["priority"]], x["id"]),
    )[:30]


def simulate(snapshot, pricing_pct=0, collection_pct=0, expenses_pct=0):
    """No claim of elasticity. Hypothetical lever changes, not projected sales."""
    baseline = snapshot["forecast"]
    if not baseline["available"]:
        return {"available": False, "reason": baseline["reason"]}
    p, c, e = (Decimal(str(n)) / Decimal(100) for n in (pricing_pct, collection_pct, expenses_pct))
    receipts = Decimal(baseline["receipts_baseline"]) * (ONE + p) * (ONE + c)
    costs = Decimal(baseline["expenses_baseline"]) * (ONE + e)
    return {
        "available": True,
        "currency": snapshot["currency"],
        "baseline_cash": baseline["cash_result_baseline"],
        "scenario_receipts": amount(receipts),
        "scenario_expenses": amount(costs),
        "scenario_cash": amount(receipts - costs),
        "difference": amount(receipts - costs - Decimal(baseline["cash_result_baseline"])),
        "assumptions": {
            "pricing_percent": pricing_pct,
            "collection_percent": collection_pct,
            "expenses_percent": expenses_pct,
        },
        "warning": (
            "Sensitivity calculation ONLY: it assumes each percentage change "
            "flows directly to receipts/costs. Real demand, capacity, conversion, "
            "churn, unrecorded costs and causation are not modeled."
        ),
    }


def pitch_playbook(client, snapshot):
    """Uses documented business context, not inferred personality or identity."""
    invoices = list(Invoice.objects.filter(client=client).values("status", "due_date", "amount"))
    engagements = list(
        Engagement.objects.filter(client=client).values(
            "kind", "status", "name", "revision_limit", "revisions_used"
        )[:10]
    )
    warning = next(
        (item for item in snapshot["client_contribution"] if item["id"] == client.id),
        None,
    )
    has_overdue = bool(warning and Decimal(warning["outstanding_overdue"]) > 0)
    has_scope_complexity = any(
        row["revision_limit"] > 0 and row["revisions_used"] >= row["revision_limit"]
        for row in engagements
    )
    advice = [
        "Start by asking about the client's measurable business outcome, deadline and budget range.",
        "Present a short problem → approach → expected deliverables → proof/acceptance structure.",
        "Offer a clear scope, revision policy, milestones and a written payment schedule.",
    ]
    if has_overdue:
        advice.insert(
            0,
            "Before pitching additional work, privately reconcile overdue invoices and agree a dated payment plan.",
        )
    if has_scope_complexity:
        advice.append(
            "Previous engagements reached revision limits: require signed change requests for extra work."
        )
    if client.status == Client.Status.BLACKLISTED:
        advice.insert(
            0,
            "The owner has explicitly restricted this account. Resolve that decision before proposing new work.",
        )
    return {
        "client_id": client.id,
        "client": client.name,
        "status": client.status,
        "recorded_engagements": len(engagements),
        "recorded_invoices": len(invoices),
        "has_overdue": has_overdue,
        "approach": advice,
        "pitch_outline": [
            "Your stated problem and its measurable impact.",
            "A defined solution with verifiable deliverables and timeline.",
            "Relevant evidence of capability; do not invent testimonials or metrics.",
            "A price or tier with explicitly included/excluded work.",
            "An agreed next step: discovery call, scoped proposal, or signed milestone.",
        ],
        "avoid": (
            "Do not make unsupported promises, pressure the client, "
            "profile personality or extend unsecured credit without owner review."
        ),
        "limitations": (
            "A structured proposal guide from internal records, not a forecast "
            "of whether this client will buy. No external market research was performed."
        ),
    }
