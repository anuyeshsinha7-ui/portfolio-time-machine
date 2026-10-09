"""Verdicts and the recommendation — transparent rules on computed numbers (brief §6.8, §6.11).

Every rule is written out in RULES so the Backing panel can show exactly how a verdict was reached.
"""
from __future__ import annotations

import numpy as np

from . import config

RULES = {
    "label_holds": "The high-risk label holds in a period if Portfolio A's Expected Shortfall (99%, historical) and its volatility are both higher than Portfolio B's.",
    "b_held_up": "Portfolio B 'held up' in a crisis if its Expected Shortfall (99%, historical) and its biggest fall were both smaller than the Nifty 50's in the same period.",
    "yes_partly_no": "Label verdict. Yes: the label held in the chosen crisis, the chosen calm period and at least 80% of all periods in the list. Partly: it held in at least one chosen period or at least half of all periods. Otherwise No.",
    "robust": "The weights are robust in a period if the share of money you would need to move to reach that period's best weights is no more than the 95th percentile of what random noise in the data alone would make you move (measured by reshuffling today's data).",
    "fit": "A portfolio fits you if its worst fall in rupees in a crisis replay (on your amount) is no bigger than the fall you said you could live with. If both fit, we suggest A because it is expected to earn more. If only B fits, we suggest B. If neither fits, we show the largest amount that keeps B's worst fall within your limit.",
    "trigger": "When to look again: review the weights when the Nifty 50's 3-month volatility goes above the lowest 3-month volatility seen during the chosen crisis.",
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
    ("Survivorship bias", "We look at today's Nifty 500 companies back to 2007, so companies that left the index or failed are missing. "
     "This matters more the further back the period goes, so the 2008 results make both portfolios look best."),
    ("Estimation error", "Expected returns and how stocks move together are worked out from only 252 days, so they are rough. The noise bands "
     "on the Rebalance screen show how much the weights move from noise alone."),
    ("Assumptions about returns", "Historical VaR assumes the past period is a fair guide. The normal method ignores extreme days. Student-t and "
     "Cornish–Fisher are approximations. Multiplying by √10 for 10 days assumes each day is independent of the last."),
    ("Costs and taxes", "We leave out brokerage, market impact, securities transaction tax and capital-gains tax."),
    ("Benchmark mismatch", "Our stock prices include reinvested dividends, but the Nifty 50 index does not, so comparisons with the Nifty slightly favour the stocks."),
    ("Data", "Any data problems we could not fix are listed in the data-quality report (on the About the data screen)."),
]


RULES["as_is"] = ("We call it recommended as it is when all four checks pass. (1) A is clearly riskier than B: the 95% "
                  "bootstrap range for A's volatility divided by B's stays above 1. (2) A is expected to earn more than a safe "
                  "Treasury bill (Sharpe above 0). (3) B moved less than the Nifty 50 over the latest 12 months. (4) Both "
                  "portfolios meet every weight limit without loosening any. If a check fails, we say 'recommended with "
                  "caution' and name the check.")


def as_is_checks(evidence: dict, P: dict, current: dict) -> list[dict]:
    """The four 'recommended as it is?' checks on today's portfolios."""
    vr = evidence["vol_ratio"]
    a, b = P["A"], P["B"]
    nifty_vol = current["B"]["nifty"]["volatility"]
    return [
        {"name": "Bold really is riskier", "ok": bool(vr["lo"] > 1),
         "detail": f"A swings {vr['ratio']:.1f}× as much as B (95% range {vr['lo']:.1f}× to {vr['hi']:.1f}×)"},
        {"name": "Bold is paid for its risk", "ok": bool(a["sharpe"] > 0),
         "detail": f"expected {a['expected_return']:.1%} a year vs {config.RISK_FREE_RATE:.1%} from a Treasury bill"},
        {"name": "Steady is calmer than the market", "ok": bool(current["B"]["volatility"] < nifty_vol),
         "detail": f"B {current['B']['volatility']:.1%} vs Nifty 50 {nifty_vol:.1%} yearly swings"},
        {"name": "All weight rules met", "ok": not (a["constraints"]["warnings"] or b["constraints"]["warnings"]),
         "detail": "2% to 25% per stock, at most 40% per sector" + ("" if not (a["constraints"]["warnings"] or b["constraints"]["warnings"])
                                                           else "; some limits had to be loosened")},
    ]


def deviation(now: dict, then: dict, conf_key: str) -> dict:
    """How VaR and ES move from today to a past period (historical method, 1-day)."""
    vn, vt = now["risk"]["Historical"][conf_key]["var"], then["risk"]["Historical"][conf_key]["var"]
    en, et = now["risk"]["Historical"][conf_key]["es"], then["risk"]["Historical"][conf_key]["es"]
    return {"var_now": vn, "var_then": vt, "var_change": vt - vn, "var_mult": vt / vn if vn else float("nan"),
            "es_now": en, "es_then": et, "es_change": et - en, "es_mult": et / en if en else float("nan")}
