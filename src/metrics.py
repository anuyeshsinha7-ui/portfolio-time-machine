"""Return and risk statistics for any window (brief §6.1).

All inputs are daily *simple* returns (a portfolio's return is then exactly Σ wᵢ rᵢ).
Annualisation uses 252 trading days.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config

T = config.TRADING_DAYS


def ann_return(r: pd.Series | pd.DataFrame):
    """Arithmetic annualised mean return = mean daily return × 252 (the μ used by Markowitz)."""
    return r.mean() * T


def cagr(r: pd.Series) -> float:
    """Compound annual growth rate of a return series."""
    r = r.dropna()
    if r.empty:
        return float("nan")
    growth = float((1 + r).prod())
    return growth ** (T / len(r)) - 1


def ann_vol(r: pd.Series | pd.DataFrame):
    """Annualised volatility = daily standard deviation × √252."""
    return r.std(ddof=1) * np.sqrt(T)


def beta(r: pd.Series, m: pd.Series) -> float:
    """Beta = Cov(r, m) / Var(m) on the days both exist."""
    both = pd.concat([r, m], axis=1).dropna()
    if len(both) < 3:
        return float("nan")
    a, b = both.iloc[:, 0].to_numpy(), both.iloc[:, 1].to_numpy()
    return float(np.cov(a, b, ddof=1)[0, 1] / np.var(b, ddof=1))


def betas(R: pd.DataFrame, m: pd.Series) -> pd.Series:
    return pd.Series({c: beta(R[c], m) for c in R.columns})


def wealth(r: pd.Series) -> pd.Series:
    return (1 + r.fillna(0)).cumprod()


def drawdown(r: pd.Series) -> pd.Series:
    """Fall from the running peak of a ₹1 investment (≤ 0)."""
    w = wealth(r)
    peak = np.maximum(w.cummax(), 1.0)
    return w / peak - 1


def max_drawdown(r: pd.Series) -> float:
    """Largest peak-to-trough fall, as a positive fraction."""
    r = r.dropna()
    if r.empty:
        return float("nan")
    return float(-drawdown(r).min())


def downside_deviation(r: pd.Series, mar_annual: float = config.RISK_FREE_RATE) -> float:
    """Annualised root-mean-square of returns below the minimum acceptable return (the risk-free rate)."""
    r = r.dropna()
    d = np.minimum(r - mar_annual / T, 0.0)
    return float(np.sqrt((d**2).mean()) * np.sqrt(T))


def sharpe(r: pd.Series, rf: float = config.RISK_FREE_RATE) -> float:
    v = ann_vol(r)
    return float((ann_return(r) - rf) / v) if v > 0 else float("nan")


def sortino(r: pd.Series, rf: float = config.RISK_FREE_RATE) -> float:
    dd = downside_deviation(r, rf)
    return float((ann_return(r) - rf) / dd) if dd > 0 else float("nan")


def skewness(r: pd.Series) -> float:
    return float(r.dropna().skew())


def excess_kurtosis(r: pd.Series) -> float:
    return float(r.dropna().kurt())


def stock_table(R: pd.DataFrame, m: pd.Series, rf: float = config.RISK_FREE_RATE) -> pd.DataFrame:
    """Every §6.1 metric for each column of R over the rows given."""
    rows = {}
    for c in R.columns:
        r = R[c].dropna()
        if len(r) < 20:
            continue
        rows[c] = {
            "ann_return": ann_return(r), "cagr": cagr(r), "volatility": ann_vol(r), "beta": beta(r, m),
            "max_drawdown": max_drawdown(r), "downside_dev": downside_deviation(r, rf),
            "sharpe": sharpe(r, rf), "sortino": sortino(r, rf), "skew": skewness(r),
            "excess_kurtosis": excess_kurtosis(r), "worst_day": float(r.min()), "days": int(len(r)),
        }
    return pd.DataFrame(rows).T


def portfolio_returns(R: pd.DataFrame, w: pd.Series) -> pd.Series:
    """Daily constant-weight (daily rebalanced) portfolio return Σ wᵢ rᵢ.

    A missing single-day return (e.g. a demerger day) contributes 0 for that stock."""
    w = w.reindex(R.columns).fillna(0.0)
    return R.fillna(0.0) @ w


def buy_and_hold_value(prices: pd.DataFrame, w: pd.Series, amount: float) -> pd.Series:
    """₹ value of a buy-and-hold portfolio bought at the first row's prices with weights w."""
    p = prices[w.index].ffill()
    units = w * amount / p.iloc[0]
    return (p * units).sum(axis=1)


def avg_pairwise_corr(R: pd.DataFrame) -> float:
    c = R.corr().to_numpy()
    n = c.shape[0]
    if n < 2:
        return float("nan")
    return float((c.sum() - np.trace(c)) / (n * (n - 1)))


def cov_matrix(R: pd.DataFrame, shrink: bool = False) -> pd.DataFrame:
    """Annualised covariance; optional Ledoit–Wolf shrinkage (see :func:`ledoit_wolf`)."""
    if shrink:
        S, _ = ledoit_wolf(R.fillna(0.0).to_numpy())
        return pd.DataFrame(S * T, index=R.columns, columns=R.columns)
    return R.cov() * T


def ledoit_wolf(X: np.ndarray) -> tuple[np.ndarray, float]:
    """Ledoit & Wolf (2004) shrinkage of the sample covariance towards a scaled identity.

    Implemented directly in NumPy (scikit-learn is not available in the browser). Returns the
    daily covariance estimate and the shrinkage intensity δ ∈ [0, 1]. Matches
    sklearn.covariance.LedoitWolf (assume_centered=False)."""
    X = np.asarray(X, dtype=float)
    n, p = X.shape
    Xc = X - X.mean(axis=0)
    S = Xc.T @ Xc / n
    mu = np.trace(S) / p
    F = mu * np.eye(p)
    d2 = np.sum((S - F) ** 2)
    # Σ_k ||x_k x_kᵀ − S||² = Σ_k ||x_k||⁴ − n·||S||²
    b2_bar = (np.sum(np.sum(Xc**2, axis=1) ** 2) - n * np.sum(S**2)) / n**2
    b2 = min(b2_bar, d2)
    delta = b2 / d2 if d2 > 0 else 0.0
    return delta * F + (1 - delta) * S, float(delta)
