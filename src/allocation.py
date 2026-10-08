"""Investment amount → rupees per stock and whole shares (brief §6.10)."""
from __future__ import annotations

import math

import pandas as pd

from . import config


def allocate(weights: pd.Series, prices: pd.Series, amount: float) -> dict:
    """₹ per stock (weight × amount), whole shares at the latest price (rounded down), money actually
    invested, leftover cash, realised weights, and the stocks the amount cannot buy."""
    w = weights[weights > 0]
    p = prices.reindex(w.index).astype(float)
    target = w * amount
    shares = (target // p).astype(int)
    invested = shares * p
    total = float(invested.sum())
    realised = invested / total if total > 0 else invested * 0
    unbuyable = [s for s in w.index if shares[s] == 0]
    table = pd.DataFrame({"weight": w, "target_rs": target, "price": p, "shares": shares,
                          "invested_rs": invested, "realised_weight": realised})
    return {"table": table, "invested": total, "cash": float(amount - total), "unbuyable": unbuyable,
            "min_sensible": min_sensible_amount(w, p)}


def min_sensible_amount(weights: pd.Series, prices: pd.Series) -> float:
    """Smallest amount that buys at least one share of every stock at its target weight:
    max over stocks of price ÷ weight, rounded up to the next ₹1,000."""
    need = (prices.reindex(weights.index) / weights).max()
    return float(math.ceil(need / 1000) * 1000)


def split_amounts(mode: str, amount_a: float, amount_b: float | None = None) -> tuple[float, float]:
    """Amounts for A and B under the three modes in config.AMOUNT_MODES."""
    if mode == "split_total":
        return amount_a / 2, amount_a / 2
    if mode == "separate":
        return amount_a, amount_b if amount_b is not None else amount_a
    return amount_a, amount_a


def rupees(loss_fraction: float, amount: float) -> float:
    """VaR/ES in ₹ = percentage × amount (linear: doubling the money doubles the rupee risk)."""
    return loss_fraction * amount


DEFAULT = config.AMOUNT_A
