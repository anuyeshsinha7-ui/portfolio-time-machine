"""Plain-language sentences generated from computed numbers (no hard-coded findings)."""
from __future__ import annotations

from .fmt import inr_short, pct


def es_finding(event_name: str, a: dict, b: dict, amount_a: float, amount_b: float, held: bool) -> str:
    ea = a["risk"]["Historical"]["0.99"]["es"]
    eb = b["risk"]["Historical"]["0.99"]["es"]
    return (f"In the {event_name}, Portfolio A's 1-day 99% Expected Shortfall was {pct(ea)} ({inr_short(ea * amount_a)} on your "
            f"{inr_short(amount_a)}) vs {pct(eb)} for B ({inr_short(eb * amount_b)}) — the high-risk label "
            f"{'held' if held else 'did not hold'}.")


def replay_finding(event_name: str, a: dict, b: dict, nifty: dict, amount_a: float, amount_b: float) -> str:
    fa, fb, fn = a["replay"]["largest_fall"], b["replay"]["largest_fall"], nifty["largest_fall"]
    return (f"Had you bought at the start of the {event_name} window, A would have fallen as far as {inr_short(fa * amount_a)} "
            f"({pct(fa)}) and B {inr_short(fb * amount_b)} ({pct(fb)}), against {pct(fn)} for the Nifty 50.")


def test2_finding(event_name: str, p: dict, regime: dict, noise_p95: float, amount: float) -> str:
    t = regime["test2"]
    sig = t["turnover"] > noise_p95
    case = {"reachable": "could still reach today's target return",
            "below_minvar": "beat today's target return with its lowest-risk portfolio",
            "unreachable": f"could not reach today's target return (the best it could do was {pct(t['r_max'])})"}[t["case"]]
    return (f"In the {event_name}, the optimiser {case} and would have rebuilt Portfolio {p['name']} with "
            f"{pct(t['turnover'], 0)} of it traded ({inr_short(t['turnover'] * amount)} on your {inr_short(amount)}) — "
            f"{'more than' if sig else 'within'} what estimation noise alone produces ({pct(noise_p95, 0)}), so "
            f"{'the allocation would genuinely change' if sig else 'our weights are not clearly wrong for that regime'}.")


def call_finding(ev: dict, amount_a: float, amount_b: float) -> str:
    a, b = ev["A"], ev["B"]
    vr = ev["vol_ratio"]
    return (f"Portfolio A swings {vr['ratio']:.1f}× as much as B (95% confidence {vr['lo']:.2f}×–{vr['hi']:.2f}×): beta {a['weighted_beta']:.2f} vs "
            f"{b['weighted_beta']:.2f}, volatility {pct(a['portfolio_vol'])} vs {pct(b['portfolio_vol'])}. "
            f"A typical bad year (one standard deviation) moves A by about {inr_short(a['portfolio_vol'] * amount_a)} "
            f"and B by {inr_short(b['portfolio_vol'] * amount_b)}.")
