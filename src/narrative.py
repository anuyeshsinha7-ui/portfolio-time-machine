"""Plain-language sentences generated from computed numbers (no hard-coded findings)."""
from __future__ import annotations

from .fmt import inr_short, pct


def es_finding(event_name: str, a: dict, b: dict, amount_a: float, amount_b: float, held: bool) -> str:
    ea = a["risk"]["Historical"]["0.99"]["es"]
    eb = b["risk"]["Historical"]["0.99"]["es"]
    return (f"In the {event_name}, Portfolio A's average loss on its worst days (1-day Expected Shortfall, 99%) was {pct(ea)}, "
            f"or {inr_short(ea * amount_a)} on your {inr_short(amount_a)}. For B it was {pct(eb)} ({inr_short(eb * amount_b)}). "
            f"So the high-risk label {'held' if held else 'did not hold'}.")


def replay_finding(event_name: str, a: dict, b: dict, nifty: dict, amount_a: float, amount_b: float) -> str:
    fa, fb, fn = a["replay"]["largest_fall"], b["replay"]["largest_fall"], nifty["largest_fall"]
    return (f"If you had bought at the start of the {event_name}, A would have fallen by up to {inr_short(fa * amount_a)} "
            f"({pct(fa)}) and B by up to {inr_short(fb * amount_b)} ({pct(fb)}). The Nifty 50 fell {pct(fn)}.")


def test2_finding(event_name: str, p: dict, regime: dict, noise_p95: float, amount: float) -> str:
    t = regime["test2"]
    sig = t["turnover"] > noise_p95
    case = {"reachable": "could still reach today's target return",
            "below_minvar": "beat today's target return with its lowest-risk portfolio",
            "unreachable": f"could not reach today's target return (the best it could do was {pct(t['r_max'])})"}[t["case"]]
    return (f"In the {event_name}, the optimiser {case}. It would have moved {pct(t['turnover'], 0)} of Portfolio {p['name']} "
            f"({inr_short(t['turnover'] * amount)} on your {inr_short(amount)}). That is "
            f"{'more than' if sig else 'within'} what random noise in the data alone causes ({pct(noise_p95, 0)}), so "
            f"{'the weights really would change in a time like that' if sig else 'there is no clear sign our weights are wrong for a time like that'}.")


def call_finding(ev: dict, amount_a: float, amount_b: float) -> str:
    a, b = ev["A"], ev["B"]
    vr = ev["vol_ratio"]
    return (f"Portfolio A swings {vr['ratio']:.1f}× as much as B (95% range {vr['lo']:.2f}× to {vr['hi']:.2f}×). Beta is "
            f"{a['weighted_beta']:.2f} for A and {b['weighted_beta']:.2f} for B. Volatility is {pct(a['portfolio_vol'])} for A and "
            f"{pct(b['portfolio_vol'])} for B. "
            f"A typical bad year (one standard deviation) moves A by about {inr_short(a['portfolio_vol'] * amount_a)} "
            f"and B by {inr_short(b['portfolio_vol'] * amount_b)}.")
