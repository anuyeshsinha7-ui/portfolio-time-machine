"""Kupiec's proportion-of-failures test and the moving-block bootstrap (brief §6.3, §6.8, §6.9)."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from . import config


def kupiec(breaches: int, n: int, c: float) -> dict:
    """Kupiec (1995) POF test. H0: the breach probability equals 1 − c.

    LR = −2 ln[(1−p)^(n−x) p^x] + 2 ln[(1−x/n)^(n−x) (x/n)^x] ~ χ²(1).
    p-value for χ²(1): P(χ² > LR) = erfc(√(LR/2))."""
    p = 1 - c
    x = int(breaches)

    def ll(prob):
        a = (n - x) * math.log(1 - prob) if n - x > 0 else 0.0
        b = x * math.log(prob) if x > 0 else 0.0
        return a + b

    phat = x / n if n else 0.0
    lr = -2 * ll(p) + (2 * ll(phat) if 0 < phat < 1 else 0.0)
    lr = max(lr, 0.0)
    pval = math.erfc(math.sqrt(lr / 2))
    return {"breaches": x, "days": n, "expected": p * n, "rate": phat, "lr": lr, "p_value": pval,
            "reject_95": pval < 0.05}


def block_indices(n: int, block: int, rng: np.random.Generator) -> np.ndarray:
    """Moving-block bootstrap: concatenate random blocks of `block` consecutive days to length n."""
    k = int(math.ceil(n / block))
    starts = rng.integers(0, n - block + 1, size=k)
    idx = (starts[:, None] + np.arange(block)[None, :]).ravel()
    return idx[:n]


def vol_ratio_ci(ra: pd.Series, rb: pd.Series, resamples: int = config.BOOTSTRAP_RESAMPLES,
                 block: int = config.BLOCK_DAYS, seed: int = config.SEED, level: float = 0.95) -> dict:
    """Block-bootstrap confidence interval for σA/σB, resampling the same dates for both."""
    both = pd.concat([ra, rb], axis=1).dropna().to_numpy()
    rng = np.random.default_rng(seed)
    n = len(both)
    ratios = np.empty(resamples)
    for i in range(resamples):
        ix = block_indices(n, block, rng)
        s = both[ix]
        ratios[i] = s[:, 0].std(ddof=1) / s[:, 1].std(ddof=1)
    lo, hi = np.quantile(ratios, [(1 - level) / 2, 1 - (1 - level) / 2])
    point = both[:, 0].std(ddof=1) / both[:, 1].std(ddof=1)
    return {"ratio": float(point), "lo": float(lo), "hi": float(hi), "resamples": resamples,
            "significant": bool(lo > 1), "draws": ratios}


def bootstrap_target_weights(R: pd.DataFrame, solve, resamples: int, block: int = config.BLOCK_DAYS,
                             seed: int = config.SEED, progress=None) -> np.ndarray:
    """Re-run ``solve(R_resampled) → weights`` on block-bootstrap resamples of the window.

    Returns an array (resamples × n). Failed solves are skipped."""
    X = R.fillna(0.0)
    rng = np.random.default_rng(seed)
    n = len(X)
    out = []
    for i in range(resamples):
        ix = block_indices(n, block, rng)
        try:
            out.append(solve(X.iloc[ix]))
        except RuntimeError:
            pass
        if progress is not None:
            progress((i + 1) / resamples)
    return np.array(out)


def breach_test(calibration: np.ndarray, test: np.ndarray, c: float, dates=None) -> dict:
    """Historical VaR calibrated on one window, breaches counted in another, Kupiec POF test."""
    from .var_es import historical

    var, _ = historical(np.asarray(calibration), c)
    test = np.asarray(test, dtype=float)
    hit = test < -var
    k = kupiec(int(hit.sum()), int(len(test)), c)
    k["var"] = var
    k["breach_dates"] = [str(d) for d, h in zip(dates, hit) if h] if dates is not None else []
    return k
