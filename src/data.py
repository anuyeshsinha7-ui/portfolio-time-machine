"""Load the committed snapshot and slice return windows (no downloads, ever)."""
from __future__ import annotations

import json
from functools import lru_cache

import numpy as np
import pandas as pd

from . import config


@lru_cache(maxsize=1)
def prices() -> pd.DataFrame:
    """Total-return (split-, bonus-, demerger- and dividend-adjusted) daily closes, Nifty 50 calendar."""
    return pd.read_csv(config.DATA_DIR / "prices.csv.gz", index_col="Date", parse_dates=["Date"])


@lru_cache(maxsize=1)
def benchmark() -> pd.DataFrame:
    return pd.read_csv(config.DATA_DIR / "benchmark.csv.gz", index_col="Date", parse_dates=["Date"])


@lru_cache(maxsize=1)
def universe() -> pd.DataFrame:
    return pd.read_csv(config.DATA_DIR / "universe.csv").set_index("symbol", drop=False)


@lru_cache(maxsize=1)
def metadata() -> dict:
    return json.loads((config.DATA_DIR / "metadata.json").read_text())


@lru_cache(maxsize=1)
def excluded_returns() -> pd.DataFrame:
    f = config.DATA_DIR / "excluded_returns.csv"
    if not f.exists():
        return pd.DataFrame(columns=["ticker", "date", "reason"])
    return pd.read_csv(f, parse_dates=["date"])


@lru_cache(maxsize=1)
def returns() -> pd.DataFrame:
    """Daily simple returns; single days whose return was dropped in cleaning are NaN."""
    R = prices().pct_change(fill_method=None)
    for _, x in excluded_returns().iterrows():
        if x["ticker"] in R.columns and x["date"] in R.index:
            R.loc[x["date"], x["ticker"]] = np.nan
    return R.iloc[1:]


@lru_cache(maxsize=1)
def market_returns() -> pd.Series:
    return benchmark()["NIFTY50"].pct_change(fill_method=None).iloc[1:].rename("NIFTY50")


def calendar() -> pd.DatetimeIndex:
    return returns().index


def window(df, start, end):
    """Rows from start to end inclusive (dates)."""
    return df.loc[pd.Timestamp(start):pd.Timestamp(end)]


def last_n(df, n: int = config.REGIME_DAYS):
    return df.iloc[-n:]


def coverage_start(symbol: str) -> pd.Timestamp:
    """First date with a return for this stock."""
    return returns()[symbol].first_valid_index()


def latest_prices() -> pd.Series:
    """Latest closing price per stock = the actual traded price (adjustments run backwards)."""
    return prices().ffill().iloc[-1]


def as_of() -> str:
    return metadata()["as_of"]
