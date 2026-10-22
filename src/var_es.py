"""Value at Risk and Expected Shortfall — three methods, as taught in class (brief §6.7).

Losses are positive fractions of the portfolio value over a 1-day horizon; 10-day figures use
√10 scaling. ES ≥ VaR and VaR(99%) ≥ VaR(95%) hold by construction (and are tested).

Methods
1. Historical simulation (primary): the class convention — the (1−c) percentile of the returns with linear
   interpolation (Excel PERCENTILE / pandas quantile), as a loss; ES = mean loss on the days at or beyond it.
2. Parametric normal: VaR = −(μ + σ z), ES = −μ + σ φ(z)/(1−c).
3. Monte Carlo, multivariate Student-t: 10,000 draws, degrees of freedom fitted to the window's
   portfolio returns (floored at 3), covariance matched to the sample, fixed seed.
"""
from __future__ import annotations

import math
from statistics import NormalDist

import numpy as np
import pandas as pd

from . import config

N = NormalDist()
METHODS = ["Historical", "Parametric normal", "Monte Carlo (Student-t)"]


def historical(r: np.ndarray, c: float) -> tuple[float, float]:
    r = np.asarray(r, dtype=float)
    r = r[~np.isnan(r)]
    q = float(np.quantile(r, 1 - c))  # linear interpolation = Excel PERCENTILE.INC = pandas .quantile (as taught in class)
    es = -float(r[r <= q].mean())  # never empty: the interpolated q is at least the worst day
    return -q, max(es, -q)


def parametric_normal(r: np.ndarray, c: float) -> tuple[float, float]:
    r = np.asarray(r, dtype=float)
    r = r[~np.isnan(r)]
    mu, sd = r.mean(), r.std(ddof=1)
    z = N.inv_cdf(1 - c)
    var = -(mu + sd * z)
    es = -mu + sd * N.pdf(z) / (1 - c)
    return float(var), float(es)


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


def all_methods(R: pd.DataFrame, w: pd.Series, cs=(0.95, 0.99)) -> dict:
    """{method: {c: {'var': x, 'es': y}}} for the constant-weight portfolio on window R."""
    port = (R.fillna(0.0) @ w.reindex(R.columns).fillna(0.0)).to_numpy()
    out = {m: {} for m in METHODS}
    for c in cs:
        v, e = historical(port, c)
        out["Historical"][c] = {"var": v, "es": e}
        v, e = parametric_normal(port, c)
        out["Parametric normal"][c] = {"var": v, "es": e}
    mc, nu = mc_student_t(R, w, cs)
    for c in cs:
        out["Monte Carlo (Student-t)"][c] = {"var": mc[c][0], "es": mc[c][1]}
    out["_t_dof"] = nu
    return out


def scale_horizon(x: float, days: int) -> float:
    """√t scaling (assumes independent, identically distributed daily returns)."""
    return x * math.sqrt(days)


def matrix_steps(R: pd.DataFrame, w: pd.Series, confs=(0.95, 0.99)) -> dict:
    """Parametric VaR by the matrix approach taught in class (8 steps, daily, sample N − 1):
    M → D = M − mean → DᵀD → Σ = DᵀD/(N−1) → w → σ²_p = wᵀΣw → μ_p = wᵀμ → VaR = μ_p + z·σ_p.

    Missing single days count as 0, exactly as in the portfolio return series, so the result equals the
    'Parametric normal' method (VaR here is the signed return, e.g. −2.5%; the app's loss is its negative)."""
    M = R.fillna(0.0)
    w = w.reindex(M.columns).fillna(0.0)
    mean = M.mean()
    D = M - mean
    DtD = D.T @ D
    n = len(M)
    Sigma = DtD / (n - 1)
    var_p = float(w @ Sigma @ w)
    mu_p = float(w @ mean)
    sd_p = math.sqrt(var_p)
    return {"M": M, "mean": mean, "sd": M.std(ddof=1), "D": D, "DtD": DtD, "n": n, "Sigma": Sigma, "w": w,
            "Sigma_w": Sigma @ w, "var_p": var_p, "sd_p": sd_p, "mu_p": mu_p,
            "var": {c: mu_p + N.inv_cdf(1 - c) * sd_p for c in confs}, "z": {c: N.inv_cdf(1 - c) for c in confs}}
