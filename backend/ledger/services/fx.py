"""Request-scoped FX lookup: one SQL query instead of per-invoice queries."""
from django.db.models import Q

from ledger.models import FxRate


def conversion_for(base: str):
    base = base.upper()
    pair_rates = {
        (rate.base.upper(), rate.quote.upper()): rate.rate
        for rate in FxRate.objects.filter(Q(base=base) | Q(quote=base))
    }

    def convert(value, currency: str):
        currency = currency.upper()
        if currency == base:
            return value
        direct = pair_rates.get((currency, base))
        if direct is not None:
            return value * direct
        inverse = pair_rates.get((base, currency))
        if inverse:
            return value / inverse
        return None

    return convert
