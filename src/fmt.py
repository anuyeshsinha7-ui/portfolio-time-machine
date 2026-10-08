"""Indian number formatting and amount parsing — one helper for the whole project (brief §9).

Pure Python (no Streamlit) so the analytics, the narrative generator, the landing-page
builder and the app all format rupees the same way.
"""
from __future__ import annotations

import math
import re

LAKH = 1_00_000
CRORE = 1_00_00_000


def group_indian(n: int) -> str:
    """1500000 → '15,00,000' (last three digits, then pairs)."""
    s = str(abs(int(n)))
    if len(s) <= 3:
        out = s
    else:
        head, tail = s[:-3], s[-3:]
        pairs = []
        while len(head) > 2:
            pairs.insert(0, head[-2:])
            head = head[:-2]
        if head:
            pairs.insert(0, head)
        out = ",".join(pairs) + "," + tail
    return ("-" if n < 0 else "") + out


def inr(x: float, decimals: int = 0) -> str:
    """₹15,00,000 (full Indian grouping). Negative amounts → '−₹…'."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "—"
    neg = x < 0
    whole_str, _, frac = f"{abs(x):.{decimals}f}".partition(".")
    s = "₹" + group_indian(int(whole_str)) + (f".{frac}" if decimals else "")
    return ("−" if neg else "") + s


def _trim(v: float, digits: int) -> str:
    s = f"{v:.{digits}f}"
    return s.rstrip("0").rstrip(".") if "." in s else s


def inr_short(x: float, digits: int = 2) -> str:
    """₹15 lakh · ₹1.25 lakh · ₹1.2 crore · ₹75,000 (below one lakh the full figure)."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "—"
    neg = x < 0
    a = abs(x)
    if a >= CRORE:
        s = f"₹{_trim(a / CRORE, digits)} crore"
    elif a >= LAKH:
        s = f"₹{_trim(a / LAKH, digits)} lakh"
    else:
        s = inr(a)
    return ("−" if neg else "") + s


def pct(x: float, digits: int = 1, sign: bool = False) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "—"
    s = f"{x * 100:+.{digits}f}%" if sign else f"{x * 100:.{digits}f}%"
    return s.replace("-", "−")


_UNITS = {
    "crore": CRORE, "crores": CRORE, "cr": CRORE, "cror": CRORE,
    "lakh": LAKH, "lakhs": LAKH, "lac": LAKH, "lacs": LAKH, "l": LAKH, "lk": LAKH,
    "thousand": 1_000, "k": 1_000,
    "million": 1_000_000, "mn": 1_000_000, "m": 1_000_000,
}


class AmountError(ValueError):
    """Raised with a plain-language message the app can show as-is."""


def parse_amount(text) -> float:
    """'15,00,000' · '15 lakh' · '1.5 crore' · '1.5cr' · '₹ 15L' · 'Rs 2,50,000' · 1500000 → rupees."""
    if isinstance(text, (int, float)) and not isinstance(text, bool):
        if math.isnan(text) or text <= 0:
            raise AmountError("Please enter an amount greater than zero.")
        return float(text)
    s = str(text or "").strip().lower()
    if not s:
        raise AmountError("Please enter an amount, for example 15,00,000 or 15 lakh.")
    s = s.replace("₹", "").replace("inr", "").replace("rs.", "").replace("rs", "").replace("rupees", "").strip()
    s = s.replace(",", "").replace("_", "").replace(" ", "")
    m = re.fullmatch(r"(\d+(?:\.\d+)?|\.\d+)([a-z]*)", s)
    if not m:
        raise AmountError(f"'{text}' doesn't look like an amount. Try 15,00,000 or 15 lakh or 1.5 crore.")
    num, unit = float(m.group(1)), m.group(2)
    if unit and unit not in _UNITS:
        raise AmountError(f"I don't recognise '{unit}'. Use lakh, crore, or a plain number.")
    value = num * _UNITS.get(unit, 1)
    if value <= 0:
        raise AmountError("Please enter an amount greater than zero.")
    return value


def validate_amount(value: float, lo: float, hi: float) -> str | None:
    """None if fine, else a plain message."""
    if value < lo:
        return f"The smallest amount we can work with is {inr(lo)}."
    if value > hi:
        return f"The largest amount this tool handles is {inr_short(hi)}."
    return None
