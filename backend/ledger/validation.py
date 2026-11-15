"""Strict persisted financial precision and currency validation."""

from decimal import Decimal

from ninja.errors import HttpError


def amount_cents(value: Decimal, label: str, allow_zero=False) -> None:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise HttpError(422, f"{label} must be a finite decimal amount.")
    if value < 0 or (value == 0 and not allow_zero):
        raise HttpError(422, f"{label} must be positive.")
    if value != value.quantize(Decimal("0.01")):
        raise HttpError(422, f"{label} must have at most two decimal places.")
    if value > Decimal("999999999999.99"):
        raise HttpError(422, f"{label} exceeds the permitted range.")


def currency_code(code: str) -> str:
    code = code.strip().upper()
    if len(code) != 3 or not code.isascii() or not code.isalpha():
        raise HttpError(422, "Currency must be a three-letter ASCII code.")
    return code
