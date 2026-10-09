"""High / Moderate / Low risk rule — "make the call" (brief §6.2).

High risk = beta ≥ 1.0 AND volatility ≥ universe median.
Low risk  = beta < 1.0 AND volatility < universe median.
Everything else = Moderate.
Composite risk score = average of the beta percentile and the volatility percentile (0–100),
used to rank stocks within each label.
"""
from __future__ import annotations

import pandas as pd

HIGH, MODERATE, LOW = "High risk", "Moderate", "Low risk"
BETA_CUT = 1.0


def label(beta: float, vol: float, vol_median: float) -> str:
    if beta >= BETA_CUT and vol >= vol_median:
        return HIGH
    if beta < BETA_CUT and vol < vol_median:
        return LOW
    return MODERATE


def classify(table: pd.DataFrame) -> pd.DataFrame:
    """Add label, percentiles and composite score to a metrics table with 'beta' and 'volatility'."""
    t = table.copy()
    med = float(t["volatility"].median())
    t["vol_median"] = med
    t["label"] = [label(b, v, med) for b, v in zip(t["beta"], t["volatility"])]
    t["beta_pct"] = t["beta"].rank(pct=True) * 100
    t["vol_pct"] = t["volatility"].rank(pct=True) * 100
    t["risk_score"] = (t["beta_pct"] + t["vol_pct"]) / 2
    return t


def rule_text(vol_median: float) -> str:
    return (f"**High risk** means beta of {BETA_CUT:.1f} or more and volatility of {vol_median:.1%} or more (the middle value "
            f"across all stocks). **Low risk** means beta below {BETA_CUT:.1f} and volatility below {vol_median:.1%}. Anything "
            "else is **Moderate**.")
