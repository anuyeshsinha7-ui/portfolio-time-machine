"""Data-cleaning checks (brief §5.2) — pure functions, local build only.

Every check takes plain pandas objects and returns the cleaned object together with a list
of :class:`Issue` records, so ``scripts/clean_data.py`` can chain them and write
``data/data_quality_report.csv``. Nothing here downloads data or imports Streamlit.

Conventions
* ``close`` is Yahoo's ``Close`` downloaded with ``auto_adjust=False``. Yahoo already divides
  it by every split it knows about, but does not adjust it for dividends.
* ``raw`` is the price actually printed on the exchange that day, rebuilt by undoing
  Yahoo's split adjustment (:func:`reconstruct_raw`).
* A *price factor* is the ratio P_ex / P_cum an action causes: a 1:1 bonus → 1/2,
  a ₹10 → ₹2 split → 1/5, a demerger that carves out 4.68% of the value → 0.9532.
"""
from __future__ import annotations

import hashlib
import math
import re
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from . import config

# ------------------------------------------------------------------ issue records


@dataclass
class Issue:
    ticker: str
    date: str
    category: str  # A_split_bonus, B_demerger, C_symbol, D_bad_print, E_calendar, F_integrity
    issue: str
    evidence: str
    action: str
    source: str = "price data"

    def as_dict(self) -> dict:
        return asdict(self)


def _d(ts) -> str:
    return "" if ts is None or (isinstance(ts, float) and math.isnan(ts)) else str(pd.Timestamp(ts).date())


def issues_frame(issues: list[Issue]) -> pd.DataFrame:
    cols = ["ticker", "date", "category", "issue", "evidence", "action", "source"]
    return pd.DataFrame([i.as_dict() for i in issues], columns=cols)


# ------------------------------------------------------------------ E. calendar


def normalise_index(df: pd.DataFrame, ticker: str) -> tuple[pd.DataFrame, list[Issue]]:
    """Plain dates (no time zone), sorted, duplicates removed (keep the last)."""
    out = df.copy()
    idx = pd.to_datetime(out.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    out.index = idx.normalize()
    out = out.sort_index()
    dup = out.index.duplicated(keep="last")
    issues = [
        Issue(ticker, _d(d), "E_calendar", "duplicate date",
              f"{int((out.index == d).sum())} rows for the same date", "kept the last row")
        for d in out.index[dup].unique()
    ]
    return out[~dup], issues


def drop_non_sessions(df: pd.DataFrame, calendar: pd.DatetimeIndex, ticker: str) -> tuple[pd.DataFrame, list[Issue]]:
    """Remove rows on dates the Nifty 50 did not trade (weekends, holidays, stray rows).

    Special sessions (Muhurat trading, budget-day Saturdays) survive automatically because
    they are in the Nifty 50 calendar.
    """
    extra = df.index.difference(calendar)
    issues = []
    for d in extra:
        kind = "weekend row" if d.weekday() >= 5 else "row on a non-trading day"
        issues.append(Issue(ticker, _d(d), "E_calendar", kind,
                            "date absent from the Nifty 50 trading calendar", "dropped"))
    return df.drop(index=extra), issues


def drop_incomplete_last_row(df: pd.DataFrame, fetched_at: pd.Timestamp, ticker: str,
                             close_time: str = "15:30") -> tuple[pd.DataFrame, list[Issue]]:
    """Drop the final row if it is today's date and the data was fetched before the close (IST)."""
    if df.empty:
        return df, []
    last = df.index[-1]
    cutoff = pd.Timestamp(f"{last.date()} {close_time}")
    if fetched_at.normalize() == last and fetched_at < cutoff:
        return df.iloc[:-1], [Issue(ticker, _d(last), "E_calendar", "incomplete trading day",
                                    f"fetched at {fetched_at:%H:%M} IST, before the {close_time} close",
                                    "dropped the last row")]
    return df, []


def align_to_calendar(close: pd.Series, calendar: pd.DatetimeIndex, ticker: str,
                      max_ffill: int = config.MAX_FFILL,
                      max_missing_pct: float = config.MAX_MISSING_PCT) -> tuple[pd.Series, list[Issue], bool]:
    """Reindex on the Nifty 50 calendar, forward-fill at most ``max_ffill`` consecutive gaps.

    Returns (aligned series, issues, keep?) — keep is False when more than ``max_missing_pct``
    of the calendar days are missing from the stock's own first date onwards.
    """
    s = close.reindex(calendar)
    first = close.first_valid_index()
    if first is None:
        return s, [Issue(ticker, "", "E_calendar", "no prices", "empty series", "excluded")], False
    span = s.loc[first:]
    missing = span.isna()
    pct = float(missing.mean())
    issues = []
    # describe gap runs
    run_id = (missing != missing.shift()).cumsum()
    for _, grp in span[missing].groupby(run_id[missing]):
        n = len(grp)
        act = f"forward-filled {n} day(s)" if n <= max_ffill else f"left {n} day(s) missing (gap longer than {max_ffill})"
        issues.append(Issue(ticker, _d(grp.index[0]), "E_calendar", "gap vs Nifty 50 calendar",
                            f"{n} consecutive trading day(s) without a price", act))
    filled = s.ffill(limit=max_ffill)
    # don't fill before the first price
    filled.loc[:first] = s.loc[:first]
    keep = pct <= max_missing_pct
    if not keep:
        issues.append(Issue(ticker, "", "E_calendar", "too many missing days",
                            f"{pct:.2%} of trading days missing (limit {max_missing_pct:.0%})", "excluded"))
    return filled, issues, keep


def stale_runs(close: pd.Series, ticker: str, flag_days: int = config.STALE_DAYS,
               exclude_days: int = config.STALE_EXCLUDE_DAYS) -> tuple[list[Issue], bool]:
    """Flag runs of ≥ ``flag_days`` identical closes; exclude the stock if a run exceeds ``exclude_days``."""
    s = close.dropna()
    same = s.eq(s.shift())
    run_id = (~same).cumsum()
    lengths = s.groupby(run_id).transform("size")
    issues, keep = [], True
    for _, grp in s.groupby(run_id):
        n = len(grp)
        if n >= flag_days:
            bad = n > exclude_days
            keep = keep and not bad
            issues.append(Issue(ticker, _d(grp.index[0]), "E_calendar", "stale price run",
                                f"{n} identical closes of {grp.iloc[0]:.2f} from {_d(grp.index[0])} to {_d(grp.index[-1])}",
                                "excluded the stock (suspended or illiquid)" if bad else "flagged; kept (possible suspension or illiquidity)"))
    del lengths
    return issues, keep


# ------------------------------------------------------------------ D. bad prints


def invalid_prices(close: pd.Series, ticker: str) -> tuple[pd.Series, list[Issue]]:
    """Zero, negative or NaN prices → missing."""
    bad = close.isna() | (close <= 0)
    issues = [Issue(ticker, _d(d), "D_bad_print", "zero, negative or missing price",
                    f"close = {close.loc[d]}", "set to missing") for d in close.index[bad & close.notna()]]
    n_nan = int(close.isna().sum())
    if n_nan:
        issues.append(Issue(ticker, _d(close.index[close.isna()][0]), "D_bad_print", "missing (NaN) prices",
                            f"{n_nan} NaN close(s) in the raw download", "left missing; handled by calendar alignment"))
    return close.where(~bad), issues


def decimal_errors(close: pd.Series, ticker: str, tol: float = 0.05) -> tuple[pd.Series, list[Issue]]:
    """Prices that jump ×10/×100 or ÷10/÷100 and revert next day → bad tick (set to missing)."""
    s = close.copy()
    issues = []
    r = s / s.shift(1)
    rn = s.shift(-1) / s
    for k in (10.0, 100.0, 0.1, 0.01):
        hit = (np.abs(r / k - 1) < tol) & (np.abs(rn * k - 1) < tol)
        for d in s.index[hit.fillna(False)]:
            issues.append(Issue(ticker, _d(d), "D_bad_print", "decimal error",
                                f"price ×{k:g} vs previous day and reverted next day ({close.loc[d]:.2f})",
                                "set to missing and forward-filled"))
            s.loc[d] = np.nan
    return s.ffill(limit=1), issues


def spike_and_revert(close: pd.Series, ticker: str, action_dates: set | None = None,
                     threshold: float = config.SPIKE_REVERT,
                     tol: float = config.SPIKE_REVERT_TOL, confirm=None) -> tuple[pd.Series, list[Issue]]:
    """|r_t| > threshold followed by r_{t+1} ≈ −r_t (within tol) and no corporate action → bad tick.

    The comparison is on log returns so a +25% spike that fully reverts (−20%) is caught;
    the tolerance is in percentage points of simple return.
    """
    action_dates = action_dates or set()
    s = close.copy()
    issues = []
    r = s.pct_change(fill_method=None)
    for i in range(1, len(s) - 1):
        rt, rn = r.iloc[i], r.iloc[i + 1]
        if pd.isna(rt) or pd.isna(rn) or abs(rt) <= threshold:
            continue
        reverts = abs((1 + rt) * (1 + rn) - 1) <= tol
        if not reverts:
            continue
        d = s.index[i]
        near_action = any(abs((pd.Timestamp(a) - d).days) <= 3 for a in action_dates)
        if near_action:
            issues.append(Issue(ticker, _d(d), "D_bad_print", "spike-and-revert near a corporate action",
                                f"r_t = {rt:+.1%}, r_t+1 = {rn:+.1%}", "kept; checked under split/demerger rules"))
            continue
        if confirm is not None and confirm(d):
            issues.append(Issue(ticker, _d(d), "D_bad_print", "spike-and-revert confirmed genuine",
                                f"r_t = {rt:+.1%}, r_t+1 = {rn:+.1%}; the exchange's official close agrees",
                                "kept (real move)", "NSE bhavcopy"))
            continue
        issues.append(Issue(ticker, _d(d), "D_bad_print", "spike-and-revert (bad tick)",
                            f"r_t = {rt:+.1%}, r_t+1 = {rn:+.1%}, no corporate action",
                            "set to missing and forward-filled"))
        s.iloc[i] = np.nan
    return s.ffill(limit=1), issues


def flag_large_moves(close: pd.Series, ticker: str, explained: dict | None = None,
                     threshold: float = config.JUMP_FLAG) -> list[Issue]:
    """Every remaining daily move beyond ±threshold, with the reason it was kept."""
    explained = explained or {}
    r = close.pct_change(fill_method=None)
    out = []
    for d in r.index[(r.abs() > threshold).fillna(False)]:
        why = explained.get(pd.Timestamp(d))
        out.append(Issue(ticker, _d(d), "D_bad_print", "daily move beyond ±20%",
                         f"r = {r.loc[d]:+.1%}",
                         f"kept — {why}" if why else "kept — no corporate action or bad-tick pattern; treated as a genuine move",
                         "price data"))
    return out


# ------------------------------------------------------------------ A. splits and bonuses


def reconstruct_raw(close: pd.Series, splits: pd.Series) -> pd.Series:
    """Undo Yahoo's split adjustment: raw_t = close_t × Π splits with ex-date after t.

    ``splits`` is Yahoo's 'Stock Splits' column (shares after / shares before, 0 = none).
    """
    ev = splits[splits.fillna(0) > 0]
    mult = pd.Series(1.0, index=close.index)
    for d, ratio in ev.items():
        mult[mult.index < d] *= float(ratio)
    return close * mult


def apply_factors(raw: pd.Series, events: list[tuple[pd.Timestamp, float]]) -> pd.Series:
    """Backward-adjust: multiply prices before each ex-date by its price factor."""
    out = raw.astype(float).copy()
    for d, f in events:
        out[out.index < pd.Timestamp(d)] *= float(f)
    return out


def nearest_ratio(r: float, ratios=None, tol: float = config.SPLIT_TOLERANCE):
    """Return the typical split/bonus price factor within ±tol of r, else None."""
    ratios = ratios or config.SPLIT_RATIOS
    for k in ratios:
        if abs(r / k - 1) <= tol:
            return k
    return None


def detect_split_jumps(price: pd.Series, tol: float = config.SPLIT_TOLERANCE) -> list[tuple[pd.Timestamp, float, float]]:
    """Days where P_t / P_{t-1} sits within ±tol of a typical split or bonus factor.

    Returns [(date, observed ratio, matched factor)].
    """
    r = price / price.shift(1)
    out = []
    for d, v in r.dropna().items():
        k = nearest_ratio(float(v), tol=tol)
        if k is not None:
            out.append((pd.Timestamp(d), float(v), k))
    return out


_BONUS = re.compile(r"bonus\s*[-:–]?\s*(\d+)\s*:\s*(\d+)", re.I)
_SPLIT = re.compile(r"(?:rs|re)\.?\s*(\d+(?:\.\d+)?)[^0-9]+?(?:rs|re)\.?\s*(\d+(?:\.\d+)?)", re.I)


def _norm_subject(s: str) -> str:
    s = " ".join(str(s).split())
    s = re.sub(r"\bsplt\b", "split", s, flags=re.I)
    s = re.sub(r"\bfrm\b", "from", s, flags=re.I)
    s = re.sub(r"\bfv spl\b", "fv split", s, flags=re.I)
    s = re.sub(r"\bbon\b", "bonus", s, flags=re.I)
    s = re.sub(r"(\d)to(re|rs)", r"\1 to \2", s, flags=re.I)
    return s


def parse_nse_action(subject: str) -> tuple[str, float | None]:
    """Classify an NSE corporate-action subject and return (kind, price factor).

    'Bonus 1:2' → ('bonus', 2/3); 'Face Value Split (Sub-Division) - From Rs 10/- Per Share To
    Rs 2/- Per Share' → ('split', 0.2); 'Bonus 1:1 And Face Value Split From Rs.10/- To Rs.5/-'
    → ('bonus', 0.25) (both factors); 'Fv Splt Frm Rs 10 To Re 1' → ('split', 0.1);
    'Demerger' → ('demerger', None)."""
    s = _norm_subject(subject)
    low = s.lower()
    if "bonus" in low and any(k in low for k in ("debenture", "deb1", "deb ", "ncrps", "preference")):
        return "other", None  # bonus debentures / preference shares, not a share bonus
    has_split = ("split" in low or "sub-division" in low or "sub division" in low) and "demerger" not in low
    if "bonus" in low:
        m = _BONUS.search(s)
        f = None
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            f = b / (a + b)
        if has_split and f is not None:
            m2 = _SPLIT.search(s[s.lower().index("split"):])
            if m2:
                old, new = float(m2.group(1)), float(m2.group(2))
                if 0 < new < old:
                    f *= new / old
        return "bonus", f
    if has_split:
        m = _SPLIT.search(s)
        if m:
            old, new = float(m.group(1)), float(m.group(2))
            if old > 0 and new > 0 and new < old:
                return "split", new / old
        return "split", None
    if "right" in low and rights_terms(s) is not None:
        return "rights", None
    if "consolidat" in low:
        return "consolidation", None
    if "demerger" in low or "de-merger" in low or "spin" in low or "scheme of arrangement" in low:
        return "demerger", None
    if "capital reduction" in low or "reduction of capital" in low or "reduction in capital" in low:
        return "capital_reduction", None
    return "other", None


_RIGHTS = re.compile(r"rights?(?:-eq| eq)?\s*[-:]?\s*(\d+)\s*:\s*(\d+)\s*@\s*(?:(par)|prem(?:ium)?\.?\s*(?:of\s*)?(?:rs|re)\.?\s*(\d+(?:\.\d+)?))", re.I)


def rights_terms(subject: str) -> tuple[int, int, float] | None:
    """'Rights 1:15 @ Premium Rs 1247' → (1, 15, 1247.0): a new shares per b held at face value + premium.
    Returns None for terms that are not a plain fully-paid rights issue (partly paid, warrants, DVRs)."""
    s = _norm_subject(subject)
    if "partly" in s.lower() or "warrant" in s.lower() or "dif vot" in s.lower():
        return None
    m = _RIGHTS.search(s)
    if not m:
        return None
    a, b = int(m.group(1)), int(m.group(2))
    prem = 0.0 if m.group(3) else float(m.group(4))
    return a, b, prem


def rights_factor(a: int, b: int, subscription: float, cum_price: float) -> float | None:
    """Theoretical ex-rights price ÷ cum-rights price: (b·P + a·S) / ((a + b)·P). None if S ≥ P."""
    if cum_price <= 0 or subscription >= cum_price:
        return None
    terp = (b * cum_price + a * subscription) / (a + b)
    return terp / cum_price


_AMOUNT = re.compile(r"(?:rs|re)\.?\s*(\d+(?:\.\d+)?)", re.I)


_PCT = re.compile(r"(\d+(?:\.\d+)?)\s*%")


def parse_nse_dividend(part: str, face_value: float | None = None) -> float | None:
    """Cash dividend per share in ₹. 'Interim Dividend - Rs 15 Per Sh' → 15.0;
    old-style 'Div Fin-130%+Spl-25%' → 155% of face value (needs face_value)."""
    low = part.lower()
    if "div" not in low:
        return None
    amounts = [float(x) for x in _AMOUNT.findall(part)]
    if amounts:
        return float(sum(amounts))
    pcts = [float(x) for x in _PCT.findall(part)]
    if pcts and face_value is not None and not pd.isna(face_value) and face_value > 0:
        return float(sum(pcts)) / 100 * float(face_value)
    return None


def nse_actions_frame(records: list[dict]) -> pd.DataFrame:
    """NSE corporate-actions JSON → one row per action part (a subject such as
    'AGM/Special Dividend - Rs 8 Per Share /Dividend - Rs 20 Per Share' gives two rows),
    with ex_date, subject, kind, factor (price factor for splits/bonuses) and dividend amount."""
    rows = []
    for r in records or []:
        ex = pd.to_datetime(r.get("exDate"), format="%d-%b-%Y", errors="coerce")
        subject = " ".join(str(r.get("subject", "")).split())
        for part in re.split(r"/(?!-)", subject):
            part = part.strip()
            if not part:
                continue
            kind, factor = parse_nse_action(part)
            fv = pd.to_numeric(r.get("faceVal"), errors="coerce")
            div = parse_nse_dividend(part, fv) if kind in ("other",) else None
            if div is not None:
                kind = "dividend"
            rows.append({"ex_date": ex, "subject": part, "kind": kind, "factor": factor,
                         "dividend": div, "symbol": r.get("symbol"), "face_value": fv})
    df = pd.DataFrame(rows, columns=["ex_date", "subject", "kind", "factor", "dividend", "symbol", "face_value"])
    return df.dropna(subset=["ex_date"]).sort_values("ex_date").reset_index(drop=True)


def nse_dividends(nse: pd.DataFrame) -> pd.Series:
    """Cash dividend per share (₹, on the share count of the day) summed by ex-date."""
    if nse is None or nse.empty:
        return pd.Series(dtype=float)
    d = nse[nse["kind"] == "dividend"].dropna(subset=["dividend"])
    return d.groupby("ex_date")["dividend"].sum()


def combined_factors(nse: pd.DataFrame) -> pd.DataFrame:
    """Splits and bonuses grouped by ex-date with their combined price factor
    (e.g. a ₹2 → ₹1 split and a 4:1 bonus on the same day → 1/2 × 1/5 = 1/10)."""
    if nse is None or nse.empty:
        return pd.DataFrame(columns=["ex_date", "factor", "subject"])
    s = nse[nse["kind"].isin(["bonus", "split"])].dropna(subset=["factor"])
    s = s.drop_duplicates(subset=["ex_date", "subject"])
    g = s.groupby("ex_date").agg(factor=("factor", "prod"), subject=("subject", " + ".join), parts=("factor", list))
    return g.reset_index()


def best_part_factor(parts: list[float], observed: float) -> float:
    """When several actions share an ex-date, the combination (product of a non-empty subset) closest, in log terms,
    to the observed price ratio — so an action that actually took effect on another day is not applied twice."""
    from itertools import combinations
    best, gap = float(np.prod(parts)), float("inf")
    for n in range(1, len(parts) + 1):
        for c in combinations(parts, n):
            f = float(np.prod(c))
            g_ = abs(np.log(observed / f))
            if g_ < gap - 1e-12:
                best, gap = f, g_
    return best


# ------------------------------------------------------------------ anchoring Yahoo to NSE official prices


def find_q_changes(q: pd.Series, tol: float = 0.01) -> tuple[list[tuple[pd.Timestamp, pd.Timestamp]], list[pd.Timestamp]]:
    """q = NSE official close ÷ Yahoo raw close at monthly checkpoints (1.0 when Yahoo is right).

    Returns (changes, outliers): ``changes`` are consecutive checkpoint pairs (a, b) between which
    q steps to a new level that persists; ``outliers`` are single checkpoints that disagree with
    both neighbours (a one-day print difference, not an adjustment)."""
    q = q.dropna()
    vals, idx = q.values, q.index
    changes, outliers = [], []
    i = 0
    while i < len(q) - 1:
        if abs(vals[i + 1] / vals[i] - 1) > tol:
            persists = i + 2 >= len(q) or abs(vals[i + 2] / vals[i + 1] - 1) <= tol
            back = i + 2 < len(q) and abs(vals[i + 2] / vals[i] - 1) <= tol
            if back and not persists:
                outliers.append(idx[i + 1])
                vals = vals.copy()
                vals[i + 1] = vals[i]
            else:
                changes.append((idx[i], idx[i + 1]))
        i += 1
    return changes, outliers


def bisect_change(dates: list, q_left: float, q_right: float, q_at) -> pd.Timestamp:
    """First date whose q is closer to ``q_right`` than to ``q_left``.

    ``dates`` are the trading days strictly after the left checkpoint, ending with the right
    checkpoint. ``q_at(date)`` returns q, or None when there is no official price that day; the
    search then probes the nearest day that has one."""
    lo, hi = -1, len(dates) - 1  # dates[lo] is on the left level, dates[hi] on the right level
    while hi - lo > 1:
        mid = (lo + hi) // 2
        probe, v = None, None
        for cand in sorted(range(lo + 1, hi), key=lambda j: abs(j - mid)):
            v = q_at(dates[cand])
            if v is not None:
                probe = cand
                break
        if probe is None:
            break
        if abs(math.log(v / q_left)) < abs(math.log(v / q_right)):
            lo = probe
        else:
            hi = probe
    return pd.Timestamp(dates[hi])


def piecewise_q(index: pd.DatetimeIndex, change_dates: list, levels: list[float]) -> pd.Series:
    """Step function: levels[0] before change_dates[0], levels[1] from it, …"""
    q = pd.Series(float(levels[0]), index=index)
    for d, lv in zip(change_dates, levels[1:]):
        q[q.index >= pd.Timestamp(d)] = float(lv)
    return q


def match_nse(nse: pd.DataFrame, when: pd.Timestamp, factor: float | None = None,
              kinds=("bonus", "split"), days: int = 7, tol: float = config.SPLIT_TOLERANCE):
    """Find the NSE action of the given kinds within ±days of ``when`` (and factor within tol)."""
    if nse is None or nse.empty:
        return None
    cand = nse[nse["kind"].isin(kinds) & ((nse["ex_date"] - when).abs() <= pd.Timedelta(days=days))]
    if factor is not None:
        ok = cand["factor"].notna() & (np.abs(cand["factor"].astype(float) / factor - 1) <= tol)
        cand_f = cand[ok]
        if not cand_f.empty:
            cand = cand_f
        elif not cand.empty and cand["factor"].notna().any():
            return None
    if cand.empty:
        return None
    cand = cand.assign(gap=(cand["ex_date"] - when).abs()).sort_values("gap")
    return cand.iloc[0]


def check_wrong_exdate(raw: pd.Series, yahoo_date: pd.Timestamp, nse_date: pd.Timestamp,
                       factor: float) -> bool:
    """True if the raw price really moved on NSE's ex-date rather than Yahoo's date."""
    if pd.Timestamp(yahoo_date) == pd.Timestamp(nse_date):
        return False
    r = raw / raw.shift(1)
    if pd.Timestamp(nse_date) not in r.index:
        return False
    return abs(r.loc[pd.Timestamp(nse_date)] / factor - 1) <= config.SPLIT_TOLERANCE


def check_double_adjustment(adjusted: pd.Series, events: list[tuple[pd.Timestamp, float]],
                            window: int = 2, tol: float = config.SPLIT_TOLERANCE) -> list[tuple[pd.Timestamp, float, str]]:
    """After adjustment, no return near an action may still equal the factor (under-adjusted)
    or its inverse (double / wrong-direction adjustment). Returns [(date, ratio, problem)]."""
    r = adjusted / adjusted.shift(1)
    out = []
    for d, f in events:
        if abs(f - 1) < 0.15:  # small factors are indistinguishable from an ordinary day's move
            continue
        d = pd.Timestamp(d)
        pos = r.index.searchsorted(d)
        lo, hi = max(1, pos - window), min(len(r), pos + window + 1)
        for j in range(lo, hi):
            v = r.iloc[j]
            if pd.isna(v):
                continue
            if abs(v / f - 1) <= tol:
                out.append((r.index[j], float(v), "still shows the action ratio (under-adjusted)"))
            elif abs(v * f - 1) <= tol:
                out.append((r.index[j], float(v), "shows the inverse ratio (double adjustment)"))
    return out


# ------------------------------------------------------------------ dividends and Adj Close check


def dividend_factor(close: pd.Series, dividends: pd.Series) -> pd.Series:
    """Backward dividend factor, Yahoo/CRSP style: on ex-date d, prices before d × (1 − D/P_{d−1})."""
    f = pd.Series(1.0, index=close.index)
    div = dividends.reindex(close.index).fillna(0.0)
    prev = close.shift(1)
    for d in div.index[div > 0]:
        p = prev.loc[d]
        if pd.isna(p) or p <= 0:
            continue
        k = 1.0 - float(div.loc[d]) / float(p)
        if 0 < k < 1:
            f[f.index < d] *= k
    return f


def suspicious_dividends(close: pd.Series, dividends: pd.Series, ticker: str, max_yield: float = 0.15) -> list[Issue]:
    """One-day dividend above ``max_yield`` of the previous close — usually a scaling error."""
    div = dividends.reindex(close.index).fillna(0.0)
    prev = close.shift(1)
    out = []
    for d in div.index[div > 0]:
        y = div.loc[d] / prev.loc[d] if prev.loc[d] and prev.loc[d] > 0 else np.nan
        if pd.notna(y) and y > max_yield:
            out.append(Issue(ticker, _d(d), "A_split_bonus", "implausible dividend",
                             f"dividend {div.loc[d]:.2f} = {y:.0%} of the previous close", "excluded from the dividend adjustment",
                             "yfinance action history"))
    return out


def compare_adjclose(mine: pd.Series, yahoo_adj: pd.Series, tol: float = config.ADJ_MISMATCH_TOL) -> pd.Series:
    """Relative gap between our rebuilt adjusted close and Yahoo's Adj Close, both rescaled to
    agree on the last common day. Returns the daily gap series (positive = ours higher)."""
    both = pd.concat([mine, yahoo_adj], axis=1, keys=["mine", "yahoo"]).dropna()
    both = both[(both > 0).all(axis=1)]
    if both.empty:
        return pd.Series(dtype=float)
    scale = both["yahoo"].iloc[-1] / both["mine"].iloc[-1]
    return both["mine"] * scale / both["yahoo"] - 1


# ------------------------------------------------------------------ B. demergers


def demerger_drop(raw: pd.Series, ex_date: pd.Timestamp) -> tuple[pd.Timestamp | None, float | None]:
    """The trading day on/after NSE's ex-date and the raw one-day price ratio on it."""
    idx = raw.index[raw.index >= pd.Timestamp(ex_date)]
    if len(idx) == 0:
        return None, None
    d = idx[0]
    pos = raw.index.get_loc(d)
    if pos == 0:
        return d, None
    prev = raw.iloc[pos - 1]
    return d, float(raw.iloc[pos] / prev) if prev and prev > 0 else None


def neutralise_day(raw: pd.Series, day: pd.Timestamp) -> tuple[pd.Series, float]:
    """Remove one day's return by rescaling the earlier history so that day shows 0% (the
    return is then also recorded as missing in data/excluded_returns.csv). Returns the factor."""
    pos = raw.index.get_loc(pd.Timestamp(day))
    f = float(raw.iloc[pos] / raw.iloc[pos - 1])
    out = raw.astype(float).copy()
    out.iloc[:pos] *= f
    return out, f


# ------------------------------------------------------------------ C. symbol changes


def stitch(new: pd.Series, old: pd.Series, change_date: pd.Timestamp,
           tol: float = config.STITCH_TOL) -> tuple[pd.Series, dict]:
    """Prepend the old symbol's history to the new symbol's.

    Joins on the first date the new series has; checks prices agree within ``tol`` on the
    overlapping days (or on the join day if they don't overlap) and rescales the old series to
    the new one at the join.
    """
    new = new.dropna()
    old = old.dropna()
    join = new.index[0]
    overlap = new.index.intersection(old.index)
    info = {"join": _d(join), "overlap_days": int(len(overlap)), "max_gap": None, "ok": False}
    if len(overlap):
        gap = (old.loc[overlap] / new.loc[overlap] - 1).abs()
        info["max_gap"] = float(gap.max())
        scale = float(new.loc[overlap[0]] / old.loc[overlap[0]])
        info["ok"] = bool(gap.max() <= tol)
    else:
        before = old[old.index < join]
        if before.empty:
            return new, info
        r = float(new.iloc[0] / before.iloc[-1] - 1)
        info["max_gap"] = abs(r)
        scale = 1.0
        info["ok"] = abs(r) <= max(tol, 0.10)  # one day apart: a normal day's move is allowed
    head = old[old.index < join] * scale
    return pd.concat([head, new]).sort_index(), info


# ------------------------------------------------------------------ F. integrity


def checksum_frame(df: pd.DataFrame) -> str:
    """SHA-256 of a DataFrame's CSV text (stable: rounded to 6 decimals, sorted)."""
    text = df.sort_index().round(6).to_csv(lineterminator="\n")
    return hashlib.sha256(text.encode()).hexdigest()


def diff_snapshots(old: pd.DataFrame, new: pd.DataFrame, tol: float = 1e-4) -> pd.DataFrame:
    """Historical prices that changed between two snapshots (Yahoo silently restating)."""
    common_c = old.columns.intersection(new.columns)
    common_i = old.index.intersection(new.index)
    a = old.loc[common_i, common_c]
    b = new.loc[common_i, common_c]
    rel = (b / a - 1).abs()
    hits = rel.stack()
    hits = hits[hits > tol]
    out = hits.rename("relative_change").reset_index()
    out.columns = ["date", "ticker", "relative_change"]
    return out
