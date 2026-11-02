from __future__ import annotations

from typing import Any


def amount_decimals(receipt: dict[str, Any]) -> int:
    amounts = [receipt[key] for key in ("subtotal", "tax", "tip", "total")]
    amounts += [
        item[key]
        for item in receipt["items"]
        for key in ("unit_price", "total_price")
    ]
    whole = all(float(a).is_integer() for a in amounts if a is not None)
    return 0 if whole else 2


def fmt(value: float | None, decimals: int) -> str:
    return "-" if value is None else f"{value:,.{decimals}f}"


def fmt_quantity(value: float | None) -> str:
    return "-" if value is None else f"{value:g}"


def escape_md(text: str) -> str:
    return text.replace("$", r"\$")