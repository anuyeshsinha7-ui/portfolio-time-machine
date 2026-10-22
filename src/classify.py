"""High / Moderate / Low risk rule — "make the call" (brief §6.2).

Not rated = negative beta (moves against the market): no label, no score, and left out of the median and the
            percentiles, so it cannot shift other stocks' scores (team decision, 22 Oct 2026).
High risk = beta ≥ 1.0 AND volatility ≥ median of the rated stocks.
Low risk  = 0 ≤ beta < 1.0 AND volatility < that median.
Everything else = Moderate.
Composite risk score = average of the beta percentile and the volatility percentile (0–100) among rated stocks,
used to rank stocks within each label.
"""
from __future__ import annotations

import pandas as pd

HIGH, MODERATE, LOW, NOT_RATED = "High risk", "Moderate", "Low risk", "Not rated"
BETA_CUT = 1.0


def label(beta: float, vol: float, vol_median: float) -> str:
    if beta < 0:
        return NOT_RATED
    if beta >= BETA_CUT and vol >= vol_median:
        return HIGH
    if beta < BETA_CUT and vol < vol_median:
        return LOW
    return MODERATE


def classify(table: pd.DataFrame) -> pd.DataFrame:
    """Add label, percentiles and composite score to a metrics table with 'beta' and 'volatility'."""
    t = table.copy()
    rated = t["beta"] >= 0
    med = float(t.loc[rated, "volatility"].median())
    t["vol_median"] = med
    t["label"] = [label(b, v, med) for b, v in zip(t["beta"], t["volatility"])]
    t["beta_pct"] = t["beta"].where(rated).rank(pct=True) * 100  # NaN (no score) for not-rated stocks
    t["vol_pct"] = t["volatility"].where(rated).rank(pct=True) * 100
    t["risk_score"] = (t["beta_pct"] + t["vol_pct"]) / 2
    return t


def rule_text(vol_median: float) -> str:
    return (f"**High risk** means beta of {BETA_CUT:.1f} or more and volatility of {vol_median:.1%} or more (the middle value "
            f"across the rated stocks). **Low risk** means beta below {BETA_CUT:.1f} and volatility below {vol_median:.1%}. Anything "
            "else is **Moderate**. A stock with a negative beta moves against the market, so it is **Not rated**: no label, "
            "no score, and it is never recommended.")
