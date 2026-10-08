"""Verdicts and the recommendation — transparent rules on computed numbers (brief §6.8, §6.11).

Every rule is written out in RULES so the Backing panel can show exactly how a verdict was reached.
"""
from __future__ import annotations

import numpy as np

RULES = {
    "label_holds": "The high-risk label holds in a period if Portfolio A's historical Expected Shortfall (99%) AND its volatility are both higher than Portfolio B's.",
    "b_held_up": "Portfolio B 'held up' in a crisis if both its historical Expected Shortfall (99%) and its maximum drawdown were smaller than the Nifty 50's in the same window.",
    "yes_partly_no": "Label verdict: Yes = held in the chosen crisis, the chosen calm period and at least 80% of all catalogue events; Partly = held in at least one chosen period or at least half of all events; otherwise No.",
    "robust": "Weights are robust in a period if the turnover needed to reach that period's optimal portfolio is within the 95th percentile of turnover produced by pure estimation noise (bootstrap of today's window).",
    "fit": "A portfolio fits you if its worst crisis-replay fall in rupees (on your amount) is no bigger than the fall you said you could live with. If both fit, A (the higher expected return) is suggested; if only B fits, B; if neither, the largest amount that keeps B's worst fall within your limit is shown.",
    "trigger": "Review trigger: revisit the weights when the Nifty 50's 3-month volatility rises above the lowest 3-month volatility seen during the chosen crisis window.",
}


def label_holds(a: dict, b: dict) -> bool:
    return (a["risk"]["Historical"]["0.99"]["es"] > b["risk"]["Historical"]["0.99"]["es"]
            and a["volatility"] > b["volatility"])


def b_held_up(b: dict) -> bool:
    return (b["risk"]["Historical"]["0.99"]["es"] < b["nifty"]["es99"]
            and b["max_drawdown"] < b["nifty"]["max_drawdown"])


def label_verdict(crisis: dict, calm: dict, board: list[dict]) -> dict:
    held_crisis = label_holds(crisis["A"], crisis["B"])
    held_calm = label_holds(calm["A"], calm["B"])
    share = float(np.mean([r["label_held"] for r in board])) if board else float("nan")
    if held_crisis and held_calm and share >= 0.8:
        v = "Yes"
    elif held_crisis or held_calm or share >= 0.5:
        v = "Partly"
    else:
        v = "No"
    return {"verdict": v, "crisis": held_crisis, "calm": held_calm, "share_all_events": share,
            "events_held": int(sum(r["label_held"] for r in board)), "events_total": len(board)}


def b_verdict(crisis: dict, board: list[dict]) -> dict:
    crises = [r for r in board if r["type"] == "crisis"]
    share = float(np.mean([r["b_held_up"] for r in crises])) if crises else float("nan")
    held = b_held_up(crisis["B"])
    v = "Yes" if held and share >= 0.8 else ("Partly" if held or share >= 0.5 else "No")
    return {"verdict": v, "crisis": held, "share_crises": share,
            "crises_held": int(sum(r["b_held_up"] for r in crises)), "crises_total": len(crises)}


def robustness(turnover_crisis: float, turnover_calm: float, noise_p95: float) -> dict:
    sig_c, sig_m = turnover_crisis > noise_p95, turnover_calm > noise_p95
    if not sig_c and not sig_m:
        v = "Robust"
    elif sig_c and sig_m:
        v = "Regime-dependent"
    else:
        v = "Partly robust"
    return {"verdict": v, "crisis_significant": bool(sig_c), "calm_significant": bool(sig_m), "noise_p95": noise_p95}


def fit(tolerance_rs: float, fall_a: float, fall_b: float, amount_a: float, amount_b: float) -> dict:
    worst_a, worst_b = fall_a * amount_a, fall_b * amount_b
    fits_a, fits_b = worst_a <= tolerance_rs, worst_b <= tolerance_rs
    if fits_a and fits_b:
        pick = "A"
    elif fits_b:
        pick = "B"
    elif fits_a:
        pick = "A"
    else:
        pick = None
    max_b = tolerance_rs / fall_b if fall_b > 0 else float("inf")
    return {"pick": pick, "fits_A": fits_a, "fits_B": fits_b, "worst_A": worst_a, "worst_B": worst_b,
            "max_amount_B": max_b}


def review_trigger(crisis_nifty_returns: list[float]) -> float:
    """Lowest 63-day annualised Nifty 50 volatility inside the crisis window."""
    r = np.asarray(crisis_nifty_returns, dtype=float)
    if len(r) < 63:
        return float(np.std(r, ddof=1) * np.sqrt(252))
    vols = [np.std(r[i - 63:i], ddof=1) * np.sqrt(252) for i in range(63, len(r) + 1)]
    return float(min(vols))


LIMITATIONS = [
    ("Survivorship bias", "Today's Nifty 200 members are looked at back to 2007, so companies that fell out of the index (or failed) are missing. "
     "The bias is stronger the further back the event — the 2008–09 results flatter both portfolios most."),
    ("Estimation error", "Expected returns and covariances from 252 days are noisy; the bootstrap bands on the Test #2 page show how much the "
     "weights move from noise alone."),
    ("Distribution assumptions", "Historical VaR assumes the past window is representative; the normal method ignores fat tails; Student-t and "
     "Cornish–Fisher are approximations. √10 scaling assumes independent days."),
    ("Costs and taxes", "No brokerage, impact costs, securities transaction tax or capital-gains tax are included."),
    ("Benchmark mismatch", "Stock prices include reinvested dividends but the Nifty 50 is a price index, so 'versus Nifty' comparisons slightly favour the stocks."),
    ("Data", "Residual data issues are listed in the data-quality report (Methodology and data page)."),
]
