"""Local-first, explainable client intelligence from recorded business evidence.

Nothing here predicts personality or uses a client's name, nationality, email,
gender, social profile or inferred protected characteristics. Comparisons use
only explicit event categories and objective ledger/payment history.
"""

from collections import Counter, defaultdict
from hashlib import sha256

from django.db import transaction
from django.db.models import Count, F, Q
from django.utils import timezone

from ledger.models import (
    Client,
    ClientIntelligenceObservation,
    ClientIntelligenceProfile,
    ClientPatternAlert,
    Event,
    Invoice,
    Payment,
)

# code: (human label, severity, recommendation). Only observable work conduct.
NEGATIVE_SIGNALS = {
    "payment_late": ("Repeated late payment", 3, "Request a deposit and shorter payment terms."),
    "scope_creep": (
        "Unapproved scope increase",
        3,
        "Use a signed change order before doing extra work.",
    ),
    "rate_haggling": (
        "Repeated rate renegotiation",
        1,
        "Agree rates and the revision policy in writing.",
    ),
    "abusive": (
        "Abusive communication recorded",
        4,
        "Preserve evidence, set boundaries and consider disengagement.",
    ),
    "chargeback": (
        "Payment chargeback",
        5,
        "Require cleared funds and document delivery acceptance.",
    ),
    "late_feedback": (
        "Slow feedback / approval",
        1,
        "Specify feedback windows and escalation contacts.",
    ),
    "missed_meeting": (
        "Missed scheduled meeting",
        1,
        "Confirm meeting attendance and milestone dates in writing.",
    ),
    "unapproved_revisions": (
        "Unapproved revisions",
        2,
        "Set revision limits and require written approval.",
    ),
    "missed_deadline": (
        "Client missed agreed deadline",
        2,
        "Add milestone dependencies and buffer time.",
    ),
    "ghosting_detected": (
        "Communication gap recorded",
        2,
        "Document follow-up attempts and payment exposure.",
    ),
    "contract_dispute": (
        "Contract terms disputed",
        4,
        "Stop scope expansion until terms are clarified in writing.",
    ),
    "invoice_overdue": (
        "Open invoice past due",
        3,
        "Follow up on overdue invoices before accepting new work.",
    ),
    "invoice_disputed": (
        "Invoice dispute",
        3,
        "Resolve the dispute with documented deliverables and acceptance.",
    ),
    "invoice_written_off": ("Written-off invoice", 4, "Avoid extending further unsecured credit."),
}
POSITIVE_SIGNALS = {
    "payment_on_time": "Payment on time",
    "rate_increase_accepted": "Accepted rate increase",
    "clear_feedback": "Timely, clear feedback",
    "scope_respected": "Scope and change control respected",
    "repeat_engagement": "Repeat engagement",
}
BEHAVIOUR_SIGNAL_CODES = tuple(x for x in NEGATIVE_SIGNALS if not x.startswith("invoice_"))
SIGNAL_WEIGHTS = {code: entry[1] for code, entry in NEGATIVE_SIGNALS.items()}


def _counts_by_client(clients):
    ids = [row.id for row in clients]
    signal_map = defaultdict(Counter)
    sample = Counter()
    observed = set(NEGATIVE_SIGNALS) | set(POSITIVE_SIGNALS)
    for row in (
        Event.objects.filter(client_id__in=ids, deleted_at__isnull=True, kind__in=observed)
        .values("client_id", "kind")
        .annotate(total=Count("id"))
    ):
        cid = row["client_id"]
        signal_map[cid][row["kind"]] += row["total"]
        sample[cid] += row["total"]

    invoices = {}
    for row in (
        Invoice.objects.filter(client_id__in=ids)
        .values("client_id")
        .annotate(
            total=Count("id"),
            overdue=Count(
                "id",
                filter=Q(
                    status__in=[Invoice.Status.SENT, Invoice.Status.PARTIAL],
                    due_date__lt=timezone.localdate(),
                ),
            ),
            disputed=Count("id", filter=Q(status=Invoice.Status.DISPUTED)),
            written_off=Count("id", filter=Q(status=Invoice.Status.WRITTEN_OFF)),
        )
    ):
        invoices[row["client_id"]] = row
        sample[row["client_id"]] += row["total"]
        cid = row["client_id"]
        for key, field in (
            ("invoice_overdue", "overdue"),
            ("invoice_disputed", "disputed"),
            ("invoice_written_off", "written_off"),
        ):
            if row[field]:
                signal_map[cid][key] = row[field]
    for row in (
        Payment.objects.filter(client_id__in=ids)
        .values("client_id")
        .annotate(
            total=Count("id"),
            late=Count("id", filter=Q(paid_on__gt=F("invoice__due_date"))),
        )
    ):
        cid = row["client_id"]
        sample[cid] += row["total"]
        # Do not double count manual and objective evidence of late payments.
        signal_map[cid]["payment_late"] = max(signal_map[cid]["payment_late"], row["late"])
    return signal_map, sample, invoices


def _public_signals(signals):
    return [
        {
            "kind": kind,
            "label": NEGATIVE_SIGNALS[kind][0],
            "count": int(count),
            "severity": NEGATIVE_SIGNALS[kind][1],
        }
        for kind, count in sorted(signals.items())
        if kind in NEGATIVE_SIGNALS and count > 0
    ]


def _risk_index(signals, score):
    severity_points = sum(
        SIGNAL_WEIGHTS[k] * min(3, int(v))
        for k, v in signals.items()
        if k in SIGNAL_WEIGHTS and v > 0
    )
    return min(100, severity_points * 4 + max(0, 60 - int(score)) // 3)


def _confidence(sample_size):
    if sample_size < 3:
        return "insufficient"
    if sample_size < 8:
        return "limited"
    if sample_size < 20:
        return "moderate"
    return "established"


def _similarity(current, past):
    """Count-aware weighted Jaccard. Two independently observed overlaps required."""
    overlap = [key for key in NEGATIVE_SIGNALS if current.get(key, 0) > 0 and past.get(key, 0) > 0]
    if len(overlap) < 2:
        return 0, []
    union = sum(
        SIGNAL_WEIGHTS[k] * max(min(3, current.get(k, 0)), min(3, past.get(k, 0)))
        for k in NEGATIVE_SIGNALS
    )
    intersection = sum(
        SIGNAL_WEIGHTS[k] * min(min(3, current.get(k, 0)), min(3, past.get(k, 0)))
        for k in NEGATIVE_SIGNALS
    )
    score = round(100 * intersection / union) if union else 0
    if score < 55:
        return 0, []
    return score, [
        {
            "kind": key,
            "label": NEGATIVE_SIGNALS[key][0],
            "current_count": int(current[key]),
            "past_count": int(past[key]),
        }
        for key in overlap
    ]


def _make_summary(client, signals, invoice, n):
    adverse = _public_signals(signals)
    risk = _risk_index(signals, client.score)
    actions = []
    for item in sorted(adverse, key=lambda s: (-s["severity"], -s["count"], s["kind"])):
        recommendation = NEGATIVE_SIGNALS[item["kind"]][2]
        if recommendation not in actions:
            actions.append(recommendation)
    if n < 3:
        actions.insert(0, "Gather more documented interactions before judging this client.")
    if not actions:
        actions = ["Record objective payment, scope and communication events to build evidence."]
    if client.score < 40:
        actions.append("Review payment exposure and contractual safeguards before taking new work.")
    return {
        "risk_index": risk,
        "evidence_confidence": _confidence(n),
        "observations": n,
        "adverse_signals": adverse,
        "positive_signals": [
            {"kind": k, "label": POSITIVE_SIGNALS[k], "count": v}
            for k, v in sorted(signals.items())
            if k in POSITIVE_SIGNALS and v > 0
        ],
        "invoice_count": invoice.get("total", 0),
        "overdue_invoices": invoice.get("overdue", 0),
        "disputed_invoices": invoice.get("disputed", 0),
        "written_off_invoices": invoice.get("written_off", 0),
        "actions": actions[:7],
        "disclaimer": "Observed business signals only, not a personality prediction or an automatic decision.",
    }


@transaction.atomic
def refresh_intelligence():
    """Build current profiles for all live clients; record daily observations and matches.

    Four fixed aggregation queries regardless of the number of clients; updates
    are transactionally consistent with their alert snapshots.
    """
    clients = list(
        Client.all_objects.order_by("created_at", "id").only(
            "id", "name", "status", "score", "created_at", "deleted_at"
        )
    )
    signals, samples, invoice_summary = _counts_by_client(clients)
    analyses = {}
    ids = [client.id for client in clients]
    existing_profiles = {
        row.client_id: row for row in ClientIntelligenceProfile.objects.filter(client_id__in=ids)
    }
    today = timezone.localdate()
    existing_observations = {
        row.client_id: row
        for row in ClientIntelligenceObservation.objects.filter(
            client_id__in=ids, observed_on=today
        )
    }
    new_profiles, changed_profiles = [], []
    new_observations, changed_observations = [], []
    assessed_at = timezone.now()
    for client in clients:
        counts = {k: int(v) for k, v in signals[client.id].items() if v > 0}
        metrics = _make_summary(
            client, counts, invoice_summary.get(client.id, {}), samples[client.id]
        )
        analyses[client.id] = {"signals": counts, "metrics": metrics}
        values = {
            "signals": counts,
            "metrics": metrics,
            "sample_size": samples[client.id],
            "score_snapshot": client.score,
        }
        prior = existing_profiles.get(client.id)
        if prior is None:
            new_profiles.append(ClientIntelligenceProfile(client_id=client.id, **values))
        elif any(getattr(prior, key) != value for key, value in values.items()):
            for key, value in values.items():
                setattr(prior, key, value)
            prior.assessed_at = assessed_at
            changed_profiles.append(prior)
        previous_observation = existing_observations.get(client.id)
        record_values = {
            "score": client.score,
            "risk_index": metrics["risk_index"],
            "evidence_count": samples[client.id],
        }
        if previous_observation is None:
            new_observations.append(
                ClientIntelligenceObservation(
                    client_id=client.id, observed_on=today, **record_values
                )
            )
        elif any(
            getattr(previous_observation, field) != value for field, value in record_values.items()
        ):
            for field, value in record_values.items():
                setattr(previous_observation, field, value)
            changed_observations.append(previous_observation)

    if new_profiles:
        ClientIntelligenceProfile.objects.bulk_create(
            new_profiles, ignore_conflicts=True, batch_size=200
        )
    if changed_profiles:
        ClientIntelligenceProfile.objects.bulk_update(
            changed_profiles,
            ["signals", "metrics", "sample_size", "score_snapshot", "assessed_at"],
            batch_size=200,
        )
    if new_observations:
        ClientIntelligenceObservation.objects.bulk_create(
            new_observations, ignore_conflicts=True, batch_size=200
        )
    if changed_observations:
        ClientIntelligenceObservation.objects.bulk_update(
            changed_observations, ["score", "risk_index", "evidence_count"], batch_size=200
        )
    existing_alerts = {
        (row.client_id, row.reference_client_id): row
        for row in ClientPatternAlert.objects.filter(client_id__in=ids)
    }

    for i, current in enumerate(clients):
        # Retired clients remain valuable historical evidence, but must not
        # receive new alerts or be presented as active prospects.
        if current.deleted_at is not None:
            continue
        current_info = analyses[current.id]
        matches = []
        if len(current_info["metrics"]["adverse_signals"]) >= 2:
            for previous in clients[:i]:
                previous_info = analyses[previous.id]
                # Comparisons require a meaningful adverse history; a neutral
                # or superficially similar client is not a risk reference.
                if (
                    previous_info["metrics"]["risk_index"] < 25
                    and previous.status != Client.Status.BLACKLISTED
                ):
                    continue
                similarity, overlap = _similarity(current_info["signals"], previous_info["signals"])
                if similarity:
                    matches.append((previous, similarity, overlap))
        matches.sort(key=lambda item: (-item[1], item[0].id))
        active_previous_ids = set()
        for previous, similarity, overlap in matches[:5]:
            active_previous_ids.add(previous.id)
            fingerprint = sha256(
                ("|".join(sorted(entry["kind"] for entry in overlap))).encode("ascii")
            ).hexdigest()
            existing = existing_alerts.get((current.id, previous.id))
            state = ClientPatternAlert.Status.OPEN
            if existing and existing.signature == fingerprint:
                state = existing.status
                if state == ClientPatternAlert.Status.RESOLVED:
                    state = ClientPatternAlert.Status.OPEN
            values = {
                "signature": fingerprint,
                "overlap": overlap,
                "similarity": similarity,
                "status": state,
            }
            if existing is None:
                entry, _ = ClientPatternAlert.objects.update_or_create(
                    client=current, reference_client=previous, defaults=values
                )
                existing_alerts[(current.id, previous.id)] = entry
            elif any(getattr(existing, key) != value for key, value in values.items()):
                for key, value in values.items():
                    setattr(existing, key, value)
                existing.save(update_fields=[*values, "updated_at"])
        stale_ids = [
            alert.id
            for (client_id, reference_id), alert in existing_alerts.items()
            if client_id == current.id
            and reference_id not in active_previous_ids
            and alert.status != ClientPatternAlert.Status.RESOLVED
        ]
        if stale_ids:
            ClientPatternAlert.objects.filter(pk__in=stale_ids).update(
                status=ClientPatternAlert.Status.RESOLVED, updated_at=assessed_at
            )
            for entry in existing_alerts.values():
                if entry.id in stale_ids:
                    entry.status = ClientPatternAlert.Status.RESOLVED
    return analyses


def local_recommendations(client_id, analyses=None):
    if analyses is None:
        analyses = refresh_intelligence()
    assessment = analyses[client_id]["metrics"]
    return {
        "provider": "local",
        "model": "deterministic-v1",
        "summary": (
            "Insufficient documented evidence to estimate business risk."
            if assessment["evidence_confidence"] == "insufficient"
            else (
                "Review documented payment, scope and communication risks."
                if assessment["risk_index"] >= 35
                else "No strong adverse pattern is present in the currently recorded evidence."
            )
        ),
        "actions": assessment["actions"],
        "risk_index": assessment["risk_index"],
        "evidence_confidence": assessment["evidence_confidence"],
        "limitations": assessment["disclaimer"],
        "evidence": assessment["adverse_signals"],
    }


def evidence_for_provider(analyses, client_id, alerts):
    """Permit only structured, de-identified behaviour counts across an opt-in boundary."""
    details = analyses[client_id]["metrics"]
    return {
        "client_reference": "selected-client",
        "score": next(
            (
                row.score_snapshot
                for row in ClientIntelligenceProfile.objects.filter(client_id=client_id)
            ),
            50,
        ),
        "risk_index": details["risk_index"],
        "evidence_confidence": details["evidence_confidence"],
        "sample_size": details["observations"],
        "behaviors": [{"code": x["kind"], "count": x["count"]} for x in details["adverse_signals"]],
        "positives": [
            {"code": x["kind"], "count": x["count"]} for x in details["positive_signals"]
        ],
        "invoice_summary": {
            key: details[key]
            for key in (
                "invoice_count",
                "overdue_invoices",
                "disputed_invoices",
                "written_off_invoices",
            )
        },
        "similarity_matches": [
            {
                "similarity_pct": alert.similarity,
                "shared_signal_codes": [x["kind"] for x in alert.overlap],
            }
            for alert in alerts[:3]
        ],
    }
