"""Stock universe: industries, market-cap buckets, history coverage, risk labels and the default picker
(brief §5.1, §6.2, §6.3)."""
from __future__ import annotations

import pandas as pd

from . import classify as CL
from . import config
from . import data as D
from . import metrics as M

T = config.TRADING_DAYS


def usable() -> pd.DataFrame:
    """Core + extended stocks with their static attributes."""
    u = D.universe()
    return u[u["status"].isin(["core", "extended"])].copy()


def metrics_table(start=None, end=None, symbols=None, require_full: bool = True) -> pd.DataFrame:
    """§6.1 metrics for every usable stock; with require_full, only stocks with (almost) the whole
    window of data between start and end."""
    R, m = D.returns(), D.market_returns()
    if start is not None:
        R, m = D.window(R, start, end), D.window(m, start, end)
    cols = symbols if symbols is not None else usable()["symbol"].tolist()
    R = R[[c for c in cols if c in R.columns]]
    if require_full:
        full = R.columns[R.iloc[: max(1, len(R) // 50)].notna().any()]  # has data at the window start
        cols = [c for c in full if R[c].notna().mean() > 0.95]
    else:
        cols = list(R.columns)
    return M.stock_table(R[cols], m)


def classification(years: int = config.CLASSIFICATION_YEARS) -> pd.DataFrame:
    """Labels on today's data (trailing `years`), with full-history values alongside."""
    cal = D.calendar()
    start = cal[-years * T]
    t = CL.classify(metrics_table(start, cal[-1]))
    u = D.universe()
    t = t.join(u[["company", "industry", "cap_bucket", "status", "first_date"]])
    full = CL.classify(metrics_table(require_full=False))  # each stock over its own available history
    t["beta_full"] = full["beta"]
    t["vol_full"] = full["volatility"]
    t["label_full"] = full["label"]
    t["window_start"] = str(start.date())
    return t.sort_values("risk_score", ascending=False)


def pick(table: pd.DataFrame, label: str, n: int = config.MIN_STOCKS, highest: bool = True,
         per_industry: int = config.MAX_PER_INDUSTRY_PICK, exclude: set | None = None,
         core_only: bool = True) -> tuple[list[str], str]:
    """Top-n by composite score within a label, at most `per_industry` per industry.
    Falls back to composite-score terciles if fewer than n qualify (logged in the note)."""
    exclude = exclude or set()
    pool = table[(table["label"] == label) & ~table.index.isin(exclude)]
    if core_only:
        pool = pool[pool["status"] == "core"]
    note = f"{label} stocks from the core universe, ranked by composite risk score"
    if len(pool) < n:
        q = table["risk_score"].quantile([1 / 3, 2 / 3])
        pool = table[(table["risk_score"] >= q.iloc[1]) if highest else (table["risk_score"] <= q.iloc[0])]
        pool = pool[~pool.index.isin(exclude)]
        note = f"fewer than {n} {label} stocks — relaxed to the composite-score tercile"
    pool = pool.sort_values("risk_score", ascending=not highest)
    chosen, count = [], {}
    for s, row in pool.iterrows():
        if count.get(row["industry"], 0) >= per_industry:
            continue
        chosen.append(s)
        count[row["industry"]] = count.get(row["industry"], 0) + 1
        if len(chosen) == n:
            break
    return chosen, note


def default_portfolios(table: pd.DataFrame | None = None) -> dict:
    table = table if table is not None else classification()
    if config.PORTFOLIO_A and config.PORTFOLIO_B:
        return {"A": list(config.PORTFOLIO_A), "B": list(config.PORTFOLIO_B), "note": "team picks from config"}
    a, na = pick(table, CL.HIGH, highest=True)
    b, nb = pick(table, CL.LOW, highest=False, exclude=set(a))
    return {"A": a, "B": b, "note_A": na, "note_B": nb}


def validate(a: list[str], b: list[str], table: pd.DataFrame) -> list[dict]:
    """Live validation badges for the picker (page 3)."""
    msgs = []
    for name, p, want in (("A", a, CL.HIGH), ("B", b, CL.LOW)):
        if len(p) < config.MIN_STOCKS:
            msgs.append({"level": "error", "text": f"Portfolio {name} needs at least {config.MIN_STOCKS} stocks (has {len(p)})."})
        if len(p) > config.MAX_STOCKS:
            msgs.append({"level": "error", "text": f"Portfolio {name} can hold at most {config.MAX_STOCKS} stocks (has {len(p)})."})
        inds = table.loc[[s for s in p if s in table.index], "industry"].nunique()
        if p and inds < 4:
            msgs.append({"level": "warning", "text": f"Portfolio {name} spans only {inds} industries; the 40% industry cap may be relaxed."})
        for s in p:
            if s in table.index and table.loc[s, "label"] != want:
                msgs.append({"level": "warning",
                             "text": f"{s} is labelled {table.loc[s, 'label']} but sits in Portfolio {name} ({want})."})
    both = set(a) & set(b)
    if both:
        msgs.append({"level": "error", "text": f"These stocks are in both portfolios: {', '.join(sorted(both))}."})
    return msgs
