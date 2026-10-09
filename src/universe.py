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


CAPS = ["Large cap", "Mid cap", "Small cap"]
FLEXI = "Flexi cap"


def _take(pool: pd.DataFrame, n: int, per_industry: int | None, chosen: list[str], count: dict) -> None:
    for s, row in pool.iterrows():
        if len(chosen) >= n:
            return
        if s in chosen:
            continue
        if per_industry is not None and count.get(row["industry"], 0) >= per_industry:
            continue
        chosen.append(s)
        count[row["industry"]] = count.get(row["industry"], 0) + 1


def pick_side(table: pd.DataFrame, label: str, sectors: list[str], caps: list[str], n: int = config.MIN_STOCKS,
              exclude: set | None = None) -> tuple[list[str], list[str]]:
    """Up to n stocks for one portfolio from the chosen sectors and market caps, ranked by the composite
    beta + standard-deviation score (highest for the bold portfolio, lowest for the steady one).

    Stocks with history back to 2007 come first so every crisis can be tested. When the choice is too narrow
    the rules are relaxed step by step, and each relaxation is returned as a plain-language note:
    1. more than 3 per sector;  2. the closest 'Moderate' stocks;  3. other market caps in the same sectors;
    4. other sectors."""
    highest = label == CL.HIGH
    exclude = exclude or set()
    t = table[~table.index.isin(exclude)].copy()
    t["_hist"] = (t["status"] != "core").astype(int)  # 0 = full history: preferred
    order = ["_hist", "risk_score"]
    asc = [True, not highest]
    in_sec = t["industry"].isin(sectors)
    in_cap = t["cap_bucket"].isin(caps)
    chosen, count, notes = [], {}, []
    _take(t[in_sec & in_cap & (t["label"] == label)].sort_values(order, ascending=asc), n,
          config.MAX_PER_INDUSTRY_PICK, chosen, count)
    steps = [
        (t[in_sec & in_cap & (t["label"] == label)], None,
         f"allowed more than {config.MAX_PER_INDUSTRY_PICK} stocks from one sector"),
        (t[in_sec & in_cap & (t["label"] == CL.MODERATE)], None,
         f"added the closest 'Moderate' stocks (not enough '{label}' stocks in your choice)"),
        (t[in_sec & ~in_cap & (t["label"] == label)], None, "added stocks from other market caps in your sectors"),
        (t[~in_sec & (t["label"] == label)], config.MAX_PER_INDUSTRY_PICK, "added stocks from other sectors"),
    ]
    for pool, cap, note in steps:
        if len(chosen) >= n:
            break
        before = len(chosen)
        _take(pool.sort_values(order, ascending=asc), n, cap, chosen, count)
        if len(chosen) > before:
            notes.append(note)
    return chosen, notes


def cap_label(caps: list[str]) -> str:
    """'Large + Small cap', or 'Flexi cap' when every size is chosen."""
    caps = [c for c in CAPS if c in caps]
    if len(caps) == len(CAPS):
        return FLEXI
    return " + ".join(c.replace(" cap", "") for c in caps) + " cap"


def pick_by_filters(table: pd.DataFrame, sectors: list[str] | None = None, cap=FLEXI,
                    n: int = config.MIN_STOCKS) -> dict:
    """Bold (A) and Steady (B) portfolios suggested from the chosen sectors and market caps.
    `cap` is a list of sizes (any combination of Large / Mid / Small cap) or a single size; 'Flexi cap' = all three."""
    sectors = sectors or sorted(table["industry"].unique())
    if isinstance(cap, str):
        caps = CAPS if cap == FLEXI else [cap]
    else:
        caps = [c for c in CAPS if c in cap] or CAPS
    cap = cap_label(caps)
    a, na = pick_side(table, CL.HIGH, sectors, caps, n)
    b, nb = pick_side(table, CL.LOW, sectors, caps, n, exclude=set(a))
    return {"A": a, "B": b, "notes_A": na, "notes_B": nb, "sectors": sectors, "cap": cap}


def default_portfolios(table: pd.DataFrame | None = None) -> dict:
    """The team's default: every sector, flexi cap."""
    table = table if table is not None else classification()
    if config.PORTFOLIO_A and config.PORTFOLIO_B:
        return {"A": list(config.PORTFOLIO_A), "B": list(config.PORTFOLIO_B), "note": "team picks from config"}
    return pick_by_filters(table)


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
