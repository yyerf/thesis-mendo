"""Integer-centavo money helpers used by the order and accounting layers."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any


CENTAVOS_PER_PESO = 100


def to_centavos(value: Any) -> int:
    """Convert a peso amount to integer centavos without binary-float drift."""
    if isinstance(value, bool):
        raise ValueError("Money value must not be boolean")
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"Invalid peso amount: {value!r}") from exc
    return int(amount * CENTAVOS_PER_PESO)


def from_centavos(value: Any) -> Decimal:
    """Return a Decimal peso amount for compatibility/display boundaries."""
    return (Decimal(int(value or 0)) / CENTAVOS_PER_PESO).quantize(Decimal("0.01"))


def format_php(value: Any, *, centavos: bool = False) -> str:
    """Format either pesos or centavos as a Philippine peso string."""
    amount = from_centavos(value) if centavos else Decimal(str(value or 0)).quantize(Decimal("0.01"))
    return f"₱{amount:,.2f}"


def safe_centavos(value: Any, default: int = 0) -> int:
    """Best-effort conversion used while migrating legacy nullable fields."""
    if value is None or value == "":
        return default
    return to_centavos(value)
