"""Regime finder: current window, automatic crisis and calm windows, and their evidence (brief §6.4)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config
from . import metrics as M

N = config.REGIME_DAYS


def current_window(cal: pd.DatetimeIndex, n: int = N) -> tuple[pd.Timestamp, pd.Timestamp]:
    return cal[-n], cal[-1]


def rolling_vol(mret: pd.Series, n: int = N) -> pd.Series:
    """Annualised rolling volatility over n days (value dated at the window end)."""
    return mret.rolling(n).std(ddof=1) * np.sqrt(config.TRADING_DAYS)


def max_dd_window(close: pd.Series) -> tuple[pd.Timestamp, pd.Timestamp, float]:
    """(peak date, trough date, fall) of the largest peak-to-trough fall inside a price series."""
    peak_val = close.cummax()
    dd = close / peak_val - 1
    trough = dd.idxmin()
    peak = close.loc[:trough].idxmax()
    return peak, trough, float(-dd.min())


def deepest_drawdown(close: pd.Series) -> tuple[pd.Timestamp, pd.Timestamp, float]:
    return max_dd_window(close)


def window_from(cal: pd.DatetimeIndex, start_pos: int, n: int = N) -> tuple[int, int]:
    start_pos = max(0, min(start_pos, len(cal) - n))
    return start_pos, start_pos + n - 1


def overlaps(a: tuple, b: tuple) -> bool:
    return not (pd.Timestamp(a[1]) < pd.Timestamp(b[0]) or pd.Timestamp(b[1]) < pd.Timestamp(a[0]))


def auto_crisis(close: pd.Series, n: int = N, pre: int = config.EVENT_PRE_DAYS) -> dict:
    """The n-day window starting `pre` days before the peak of the deepest Nifty 50 drawdown."""
    cal = close.index
    peak, trough, fall = deepest_drawdown(close)
    p = cal.get_loc(peak)
    s, e = window_from(cal, p - pre, n)
    return {"start": cal[s], "end": cal[e], "peak": peak, "trough": trough, "fall": fall}


def auto_calm(mret: pd.Series, exclude: list[tuple], n: int = N) -> dict:
    """The n-day window, overlapping none of `exclude`, with the lowest Nifty 50 realised volatility."""
    rv = rolling_vol(mret, n).dropna()
    cal = mret.index
    for end in rv.sort_values().index:
        e = cal.get_loc(end)
        w = (cal[e - n + 1], end)
        if not any(overlaps(w, x) for x in exclude):
            return {"start": w[0], "end": w[1], "vol": float(rv.loc[end])}
    raise RuntimeError("no calm window found")


def window_stats(close: pd.Series, mret: pd.Series, start, end) -> dict:
    c = close.loc[start:end]
    r = mret.loc[start:end]
    from .var_es import historical
    v99, es99 = historical(r.to_numpy(), 0.99)
    return {"start": str(pd.Timestamp(start).date()), "end": str(pd.Timestamp(end).date()),
            "return": float(c.iloc[-1] / c.iloc[0] - 1), "volatility": float(M.ann_vol(r)),
            "max_drawdown": M.max_drawdown(r), "worst_day": float(r.min()), "var99": v99, "es99": es99,
            "days": int(len(r))}


def candidates(close: pd.Series, mret: pd.Series, kind: str, exclude: list[tuple], k: int = 3,
               n: int = N, step: int = 5) -> list[dict]:
    """Top-k non-overlapping n-day windows: deepest drawdown (crisis) or lowest volatility (calm)."""
    cal = close.index
    scored = []
    for e in range(n - 1, len(cal), step):
        s = e - n + 1
        w = (cal[s], cal[e])
        if any(overlaps(w, x) for x in exclude):
            continue
        if kind == "crisis":
            score = -M.max_drawdown(mret.iloc[s:e + 1])
        else:
            score = float(mret.iloc[s:e + 1].std(ddof=1))
        scored.append((score, w))
    scored.sort(key=lambda x: x[0])
    picked = []
    for score, w in scored:
        if all(not overlaps(w, p) for p in picked):
            picked.append(w)
        if len(picked) == k:
            break
    return [window_stats(close, mret, a, b) for a, b in picked]
