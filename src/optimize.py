"""Markowitz optimisation with scipy.optimize (brief §6.6, §6.9).

Constraints, identical in every window:
  Σ w = 1;  W_MIN ≤ wᵢ ≤ W_MAX;  Σ_{i ∈ industry} wᵢ ≤ INDUSTRY_MAX.
Every solve uses SLSQP with tight tolerances from several starting points and is followed by an
explicit constraint check. Local tests cross-check against cvxpy.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.optimize import linprog, minimize

from . import config

TOL = 1e-6


@dataclass
class Constraints:
    w_min: float
    w_max: float
    ind_max: float
    groups: dict  # industry → list of asset positions
    warnings: list = field(default_factory=list)

    def A_ind(self, n: int) -> np.ndarray:
        A = np.zeros((len(self.groups), n))
        for k, idx in enumerate(self.groups.values()):
            A[k, idx] = 1.0
        return A


def build_constraints(industries: list[str], w_min: float = config.W_MIN, w_max: float = config.W_MAX,
                      ind_max: float = config.INDUSTRY_MAX) -> Constraints:
    """Constraints for assets with the given industries; relaxed (with a visible warning) if infeasible."""
    n = len(industries)
    groups: dict = {}
    for i, ind in enumerate(industries):
        groups.setdefault(ind, []).append(i)
    warn = []
    if n * w_min > 1 + 1e-12:
        new = np.floor(1 / n * 1e4) / 1e4
        warn.append(f"Minimum weight relaxed from {w_min:.1%} to {new:.2%}: {n} stocks × {w_min:.0%} exceeds 100%.")
        w_min = new
    if n * w_max < 1 - 1e-12:
        new = np.ceil(1 / n * 1e4) / 1e4
        warn.append(f"Maximum weight relaxed from {w_max:.0%} to {new:.2%}: {n} stocks × {w_max:.0%} is below 100%.")
        w_max = new
    sizes = {g: len(ix) for g, ix in groups.items()}
    need_min = max(m * w_min for m in sizes.values())
    if need_min > ind_max + 1e-12:
        warn.append(f"Industry cap relaxed from {ind_max:.0%} to {need_min:.0%}: one industry's minimum weights alone exceed the cap.")
        ind_max = need_min
    # can the caps hold 100% at all?
    def capacity(cap):
        return sum(min(cap, m * w_max) for m in sizes.values())
    if capacity(ind_max) < 1 - 1e-12:
        cap = ind_max
        while capacity(cap) < 1 - 1e-12 and cap < 1:
            cap += 0.01
        warn.append(f"Industry cap relaxed from {ind_max:.0%} to {cap:.0%}: too few industries to place 100% under the cap.")
        ind_max = cap
    return Constraints(float(w_min), float(w_max), float(ind_max), groups, warn)


def check(w: np.ndarray, cons: Constraints) -> list[str]:
    """Every violated constraint (empty list = feasible)."""
    w = np.asarray(w, dtype=float)
    out = []
    if abs(w.sum() - 1) > TOL:
        out.append(f"weights sum to {w.sum():.8f}")
    if (w < cons.w_min - TOL).any():
        out.append(f"weight below {cons.w_min:.2%}")
    if (w > cons.w_max + TOL).any():
        out.append(f"weight above {cons.w_max:.2%}")
    for g, idx in cons.groups.items():
        if w[idx].sum() > cons.ind_max + TOL:
            out.append(f"{g} at {w[idx].sum():.2%} > {cons.ind_max:.0%}")
    return out


def _scipy_constraints(cons: Constraints, n: int, mu=None, target=None):
    A = cons.A_ind(n)
    cl = [{"type": "eq", "fun": lambda w: w.sum() - 1.0, "jac": lambda w: np.ones_like(w)},
          {"type": "ineq", "fun": lambda w: cons.ind_max - A @ w, "jac": lambda w: -A}]
    if target is not None:
        cl.append({"type": "ineq", "fun": lambda w: mu @ w - target, "jac": lambda w: mu})
    return cl


def random_feasible(n: int, cons: Constraints, k: int, seed: int = config.SEED, max_batches: int = 200) -> np.ndarray:
    """Up to k random portfolios satisfying every constraint (Dirichlet on the free weight, rejection)."""
    rng = np.random.default_rng(seed)
    free = 1 - n * cons.w_min
    A = cons.A_ind(n)
    out = []
    got = 0
    for _ in range(max_batches):
        alpha = rng.choice([0.3, 1.0, 3.0])
        d = rng.dirichlet(np.full(n, alpha), size=max(k, 500))
        W = cons.w_min + free * d
        ok = (W <= cons.w_max + 1e-12).all(axis=1) & ((W @ A.T) <= cons.ind_max + 1e-12).all(axis=1)
        W = W[ok]
        if len(W):
            out.append(W)
            got += len(W)
        if got >= k:
            break
    if not out:
        return np.empty((0, n))
    return np.vstack(out)[:k]


def _starts(n, cons, extra=None, k=4):
    s = [np.full(n, 1 / n)]
    if k > 0:
        s += list(random_feasible(n, cons, k, seed=config.SEED + 7))
    if extra is not None:
        s.insert(0, np.asarray(extra, dtype=float))
    return s


def _solve(obj, jac, n, cons, mu=None, target=None, x0=None, starts=4):
    bounds = [(cons.w_min, cons.w_max)] * n
    best = None
    for s in _starts(n, cons, x0, starts):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)  # SLSQP clips steps to the bounds; checked below
            res = minimize(obj, s, jac=jac, method="SLSQP", bounds=bounds,
                           constraints=_scipy_constraints(cons, n, mu, target),
                           options={"ftol": 1e-14, "maxiter": 1000})
        w = np.clip(res.x, cons.w_min, cons.w_max)
        w = w / w.sum()
        viol = check(w, cons)
        if target is not None and mu @ w < target - 1e-7:
            viol.append("target return missed")
        if viol:
            continue
        val = obj(w)
        if best is None or val < best[0] - 1e-12:
            best = (val, w)
    if best is None:
        raise RuntimeError("No feasible solution found")
    return best[1]


def min_variance(mu, S, cons: Constraints, x0=None, starts: int = 4) -> np.ndarray:
    S = np.asarray(S)
    return _solve(lambda w: w @ S @ w, lambda w: 2 * S @ w, len(S), cons, x0=x0, starts=starts)


def max_sharpe(mu, S, cons: Constraints, rf: float = config.RISK_FREE_RATE, x0=None) -> tuple[np.ndarray, bool]:
    """Maximum-Sharpe weights. Returns (weights, fell_back) — falls back to minimum variance when no
    feasible portfolio earns more than the risk-free rate."""
    mu, S = np.asarray(mu), np.asarray(S)
    n = len(mu)
    rmax, _ = max_return(mu, cons)
    if rmax <= rf:
        return min_variance(mu, S, cons), True

    def f(w):
        sd = np.sqrt(w @ S @ w)
        return -(mu @ w - rf) / sd

    def g(w):
        sd = np.sqrt(w @ S @ w)
        ex = mu @ w - rf
        return -(mu * sd - ex * (S @ w) / sd) / sd**2

    w = _solve(f, g, n, cons, x0=x0, starts=6)
    return w, False


def target_return(mu, S, cons: Constraints, target: float, x0=None, starts: int = 4) -> np.ndarray:
    S = np.asarray(S)
    return _solve(lambda w: w @ S @ w, lambda w: 2 * S @ w, len(S), cons, mu=np.asarray(mu), target=target,
                  x0=x0, starts=starts)


def max_return(mu, cons: Constraints) -> tuple[float, np.ndarray]:
    """R_max: the highest return reachable under the constraints (linear program)."""
    mu = np.asarray(mu)
    n = len(mu)
    A = cons.A_ind(n)
    res = linprog(-mu, A_ub=A, b_ub=np.full(len(A), cons.ind_max), A_eq=np.ones((1, n)), b_eq=[1.0],
                  bounds=[(cons.w_min, cons.w_max)] * n, method="highs")
    if not res.success:
        raise RuntimeError(f"linprog failed: {res.message}")
    return float(mu @ res.x), res.x


def port_stats(w, mu, S, rf: float = config.RISK_FREE_RATE) -> dict:
    w = np.asarray(w)
    r = float(np.asarray(mu) @ w)
    v = float(np.sqrt(w @ np.asarray(S) @ w))
    return {"ret": r, "vol": v, "sharpe": (r - rf) / v if v > 0 else float("nan")}


def frontier(mu, S, cons: Constraints, points: int = config.FRONTIER_POINTS) -> dict:
    """Efficient frontier from the minimum-variance portfolio to R_max."""
    mu, S = np.asarray(mu), np.asarray(S)
    w_mv = min_variance(mu, S, cons)
    r_min = float(mu @ w_mv)
    r_max, w_rmax = max_return(mu, cons)
    targets = np.linspace(r_min, r_max, points)
    rets, vols, ws = [], [], []
    prev = w_mv
    for t in targets:
        try:
            w = target_return(mu, S, cons, float(t), x0=prev, starts=0) if t > r_min + 1e-10 else w_mv
        except RuntimeError:
            w = w_rmax if t >= r_max - 1e-9 else prev
        prev = w
        st = port_stats(w, mu, S)
        rets.append(st["ret"])
        vols.append(st["vol"])
        ws.append(w)
    return {"r_min": r_min, "r_max": r_max, "w_minvar": w_mv, "rets": np.array(rets), "vols": np.array(vols),
            "weights": np.array(ws)}


def efficient_vol_at(fr: dict, r: float) -> float:
    """Volatility of the efficient portfolio with return r (interpolated on the frontier)."""
    if r <= fr["r_min"]:
        return float(fr["vols"][0])
    if r >= fr["r_max"]:
        return float(fr["vols"][-1])
    return float(np.interp(r, fr["rets"], fr["vols"]))


def cloud(mu, S, cons: Constraints, k: int = config.RANDOM_PORTFOLIOS, seed: int = config.SEED) -> pd.DataFrame:
    mu, S = np.asarray(mu), np.asarray(S)
    W = random_feasible(len(mu), cons, k, seed)
    r = W @ mu
    v = np.sqrt(np.einsum("ij,jk,ik->i", W, S, W))
    return pd.DataFrame({"ret": r, "vol": v, "sharpe": (r - config.RISK_FREE_RATE) / v})


def target_case(target: float, r_minvar: float, r_max: float) -> str:
    """Which §6.9 case applies in a regime."""
    if target > r_max + 1e-9:
        return "unreachable"
    if target < r_minvar - 1e-9:
        return "below_minvar"
    return "reachable"


def solve_target_case(mu, S, cons: Constraints, target: float, starts: int = 4) -> dict:
    """§6.9: minimise variance s.t. μ·w ≥ min(target, R_max); report which case applied."""
    mu, S = np.asarray(mu), np.asarray(S)
    w_mv = min_variance(mu, S, cons, starts=starts)
    r_mv = float(mu @ w_mv)
    r_max, w_rmax = max_return(mu, cons)
    case = target_case(target, r_mv, r_max)
    if case == "below_minvar":
        w = w_mv
    elif case == "unreachable":
        try:
            w = target_return(mu, S, cons, r_max - 1e-9, x0=w_rmax, starts=starts)
        except RuntimeError:
            w = w_rmax
    else:
        w = target_return(mu, S, cons, target, x0=w_mv, starts=starts)
    return {"weights": w, "case": case, "r_minvar": r_mv, "r_max": r_max, **port_stats(w, mu, S)}


def turnover(w_a, w_b) -> float:
    """½ Σ |Δw| — the share of the portfolio you would have to trade."""
    return float(0.5 * np.abs(np.asarray(w_a) - np.asarray(w_b)).sum())
