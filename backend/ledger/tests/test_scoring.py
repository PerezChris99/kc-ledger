from datetime import date, timedelta
from ledger.services.scoring import compute_client_score

TODAY = date(2026, 10, 28)

def test_score_is_bounded_and_explainable():
    result = compute_client_score({"status": "active"}, TODAY).as_dict()
    assert 0 <= result["score"] <= 100
    assert len(result["factors"]) == 8
    assert all({"key", "label", "maximum", "points", "detail", "verdict"} <= set(f) for f in result["factors"])

def test_blacklisted_client_scores_zero():
    assert compute_client_score({"status": "blacklisted"}, TODAY).score == 0

def test_disputed_invoice_penalty():
    result = compute_client_score({"invoices": [{"amount": 100, "status": "disputed"}]}, TODAY)
    assert any(p["key"] == "disputed_invoices" and p["points"] == 6 for p in result.penalties)

def test_overdue_invoice_reduces_outstanding_factor():
    base = compute_client_score({"invoices": []}, TODAY)
    risky = compute_client_score({"invoices": [{"amount": 100, "outstanding": 100, "status": "sent", "due_date": TODAY - timedelta(days=10)}]}, TODAY)
    assert next(f for f in risky.factors if f.key == "outstanding_risk").points < next(f for f in base.factors if f.key == "outstanding_risk").points
