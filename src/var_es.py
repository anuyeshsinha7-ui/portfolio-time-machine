"""Value at Risk and Expected Shortfall — four methods (brief §6.7).

Losses are positive fractions of the portfolio value over a 1-day horizon; 10-day figures use
√10 scaling. ES ≥ VaR and VaR(99%) ≥ VaR(95%) hold by construction (and are tested).

Methods
1. Historical simulation (primary): the empirical loss quantile; ES = mean loss beyond it.
2. Parametric normal: VaR = −(μ + σ z), ES = −μ + σ φ(z)/(1−c).
3. Monte Carlo, multivariate Student-t: 10,000 draws, degrees of freedom fitted to the window's
   portfolio returns (floored at 3), covariance matched to the sample, fixed seed.
4. Cornish–Fisher: the normal quantile corrected for skewness and excess kurtosis; ES by averaging
   the (monotone) Cornish–Fisher quantile over the tail.
"""
from __future__ import annotations

import math
from statistics import NormalDist

import numpy as np
import pandas as pd

from . import config

N = NormalDist()
METHODS = ["Historical", "Parametric normal", "Monte Carlo (Student-t)", "Cornish–Fisher"]


def historical(r: np.ndarray, c: float) -> tuple[float, float]:
    r = np.sort(np.asarray(r, dtype=float)[~np.isnan(r)])
    n = len(r)
    k = max(int(math.floor(round(n * (1 - c), 9))), 1)  # number of tail observations
    var = -r[k - 1] if k <= n else float("nan")
    # tail = worst k observations (losses at least as bad as VaR)
    es = -r[:k].mean()
    return float(var), float(max(es, var))


def parametric_normal(r: np.ndarray, c: float) -> tuple[float, float]:
    r = np.asarray(r, dtype=float)
    r = r[~np.isnan(r)]
    mu, sd = r.mean(), r.std(ddof=1)
    z = N.inv_cdf(1 - c)
    var = -(mu + sd * z)
    es = -mu + sd * N.pdf(z) / (1 - c)
    return float(var), float(es)


_GRID = 1600
_PS = (np.arange(_GRID) + 0.5) / _GRID
_Z = np.array([N.inv_cdf(float(x)) for x in _PS])


def _cf_quantile(z: np.ndarray, s: float, k: float) -> np.ndarray:
    return z + (z**2 - 1) * s / 6 + (z**3 - 3 * z) * k / 24 - (2 * z**3 - 5 * z) * s**2 / 36


def cornish_fisher(r: np.ndarray, c: float, grid: int = 400) -> tuple[float, float]:
    r = np.asarray(r, dtype=float)
    r = r[~np.isnan(r)]
    mu, sd = r.mean(), r.std(ddof=1)
    s = float(pd.Series(r).skew())
    k = float(pd.Series(r).kurt())
    # monotone rearrangement of the CF quantile function over (0, 1) so ES ≥ VaR always holds
    q_all = np.sort(_cf_quantile(_Z, s, k))
    q_at = float(np.interp(1 - c, _PS, q_all))
    var = -(mu + sd * q_at)
    tail_ps = (np.arange(grid) + 0.5) / grid * (1 - c)
    tail_q = np.interp(tail_ps, _PS, q_all)
    es = -(mu + sd * float(tail_q.mean()))
    return float(var), float(max(es, var))


def fit_t_dof(r: np.ndarray, floor: float = config.T_DOF_FLOOR) -> float:
    """Student-t degrees of freedom by maximum likelihood on standardised returns (floored)."""
    from scipy import optimize, special

    r = np.asarray(r, dtype=float)
    r = r[~np.isnan(r)]
    x = (r - r.mean()) / r.std(ddof=1)

    def nll(nu):
        # t scaled to unit variance: scale = sqrt((nu-2)/nu)
        sc = math.sqrt((nu - 2) / nu)
        z = x / sc
        ll = (special.gammaln((nu + 1) / 2) - special.gammaln(nu / 2) - 0.5 * math.log(nu * math.pi)
              - math.log(sc) - (nu + 1) / 2 * np.log1p(z**2 / nu))
        return -float(ll.sum())

    res = optimize.minimize_scalar(nll, bounds=(2.05, 200.0), method="bounded")
    return float(max(res.x, floor))


def mc_student_t(R: pd.DataFrame, w: pd.Series, cs, draws: int = config.MC_DRAWS,
                 seed: int = config.SEED, dof: float | None = None) -> tuple[dict, float]:
    """Simulate multivariate-t asset returns with the sample mean and covariance; return
    {c: (VaR, ES)} for the portfolio and the fitted degrees of freedom."""
    X = R.fillna(0.0).to_numpy()
    wv = w.reindex(R.columns).fillna(0.0).to_numpy()
    mu = X.mean(axis=0)
    S = np.cov(X, rowvar=False, ddof=1)
    port = X @ wv
    nu = fit_t_dof(port) if dof is None else dof
    rng = np.random.default_rng(seed)
    scale = S * (nu - 2) / nu  # covariance of t = scale × ν/(ν−2) → matches S
    L = np.linalg.cholesky(scale + 1e-12 * np.eye(len(wv)))
    Z = rng.standard_normal((draws, len(wv))) @ L.T
    g = rng.chisquare(nu, size=(draws, 1)) / nu
    sims = mu + Z / np.sqrt(g)
    p = sims @ wv
    out = {c: historical(p, c) for c in cs}
    return out, nu


def all_methods(R: pd.DataFrame, w: pd.Series, cs=(0.95, 0.99, config.ES_BASEL)) -> dict:
    """{method: {c: {'var': x, 'es': y}}} for the constant-weight portfolio on window R."""
    port = (R.fillna(0.0) @ w.reindex(R.columns).fillna(0.0)).to_numpy()
    out = {m: {} for m in METHODS}
    for c in cs:
        v, e = historical(port, c)
        out["Historical"][c] = {"var": v, "es": e}
        v, e = parametric_normal(port, c)
        out["Parametric normal"][c] = {"var": v, "es": e}
        v, e = cornish_fisher(port, c)
        out["Cornish–Fisher"][c] = {"var": v, "es": e}
    mc, nu = mc_student_t(R, w, cs)
    for c in cs:
        out["Monte Carlo (Student-t)"][c] = {"var": mc[c][0], "es": mc[c][1]}
    out["_t_dof"] = nu
    return out


def scale_horizon(x: float, days: int) -> float:
    """√t scaling (assumes independent, identically distributed daily returns)."""
    return x * math.sqrt(days)
