"""Clean the raw downloads into the committed snapshot (brief §5.2).

Pipeline per stock (each step is a pure function in src/cleaning.py; every detection and fix
lands in data/data_quality_report.csv):

  E  normalise dates, drop duplicates / non-sessions / an incomplete last day
  D  zero, negative or NaN prices → missing
  A  undo Yahoo's split adjustment → Yahoo "raw"; anchor it to NSE's official closes at monthly
     checkpoints (bisecting to the exact day wherever Yahoo's level jumps) → true exchange prices
  A  rebuild every split/bonus adjustment from NSE corporate actions (confirmed in the prices),
     check for double adjustment and wrong ex-dates, compare with Yahoo's own split records
  B  demergers / capital reductions: official ratio from data/demerger_ratios.csv if researched,
     otherwise drop that single day's return (data/excluded_returns.csv)
  D  decimal errors, spike-and-revert bad ticks, every remaining move beyond ±20% explained
  A  dividend adjustment from NSE's dividend records → total-return price; compare with Yahoo's Adj Close
  E  align to the Nifty 50 calendar, forward-fill ≤ 2 days, missing-days and stale-price rules
  F  checksum, diff against the previous snapshot, ≥ 20 random spot-checks against NSE bhavcopies

Outputs (committed): data/prices.csv.gz, data/benchmark.csv.gz, data/universe.csv,
data/metadata.json, data/data_quality_report.csv, data/corporate_actions.csv,
data/symbol_changes.csv, data/excluded_returns.csv, data/nse_anchor.csv, data/spot_checks.csv
and docs/DATA_QUALITY.md.
"""
from __future__ import annotations

import json
import random
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from src import cleaning as C  # noqa: E402
from src import config  # noqa: E402
import nse_bhavcopy as NB  # noqa: E402

RAW = config.RAW_DIR
DATA = config.DATA_DIR
YF = RAW / "yahoo"
START = pd.Timestamp(config.HISTORY_START)
MIN_EXTENDED_DAYS = 3 * config.TRADING_DAYS  # enough for the 3-year risk label
ANCHOR_TOL = 0.01
DEMERGER_REL_DROP = -0.03

issues: list[C.Issue] = []
STALE_MARKET_DAYS: list[pd.Timestamp] = []


def log(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------- inputs
def read_yahoo(ticker: str) -> pd.DataFrame | None:
    f = YF / f"{ticker}.csv"
    if not f.exists():
        man = DATA / "manual_csv" / f"{ticker.replace('.NS', '')}.csv"
        if man.exists():
            df = pd.read_csv(man, parse_dates=["Date"], index_col="Date")
            for c in ("Dividends", "Stock Splits"):
                df[c] = 0.0
            return df
        return None
    return pd.read_csv(f, parse_dates=["Date"], index_col="Date")


def load_symbol_changes() -> pd.DataFrame:
    raw = pd.read_csv(RAW / "nse" / "symbolchange.csv", header=None, encoding="latin-1",
                      names=["company", "old", "new", "date"], skiprows=1)
    raw = raw.dropna(subset=["old", "new"])
    for c in ("company", "old", "new"):
        raw[c] = raw[c].astype(str).str.strip()
    raw["date"] = pd.to_datetime(raw["date"].astype(str).str.strip(), format="%d-%b-%Y", errors="coerce")
    return raw.dropna(subset=["date"])


def symbol_chain(sym: str, changes: pd.DataFrame) -> list[tuple[str, pd.Timestamp, str]]:
    """[(old_symbol, date it changed to the next symbol, company)], newest first."""
    chain, cur, seen = [], sym, set()
    while cur not in seen:
        seen.add(cur)
        hit = changes[changes["new"] == cur]
        if hit.empty:
            break
        row = hit.sort_values("date").iloc[-1]
        chain.append((row["old"], row["date"], row["company"]))
        cur = row["old"]
    return chain


def nse_symbol_on(sym: str, d: pd.Timestamp, chain) -> str:
    """The symbol the stock traded under on NSE on date d."""
    cur = sym
    for old, when, _ in chain:  # newest change first
        if d < when:
            cur = old
        else:
            break
    return cur


def load_nse_ca(sym: str, chain) -> pd.DataFrame:
    recs = []
    for s in [sym] + [c[0] for c in chain]:
        f = RAW / "nse_ca" / f"{s}.json"
        if f.exists():
            try:
                recs += json.loads(f.read_text())
            except json.JSONDecodeError:
                pass
    df = C.nse_actions_frame(recs)
    return df.drop_duplicates(subset=["ex_date", "subject"]).reset_index(drop=True)


def load_demerger_ratios() -> pd.DataFrame:
    f = DATA / "demerger_ratios.csv"
    if not f.exists():
        return pd.DataFrame({"ticker": pd.Series(dtype=str), "ex_date": pd.Series(dtype="datetime64[ns]"),
                             "factor": pd.Series(dtype=float), "basis": pd.Series(dtype=str),
                             "source": pd.Series(dtype=str)})
    df = pd.read_csv(f, comment="#", parse_dates=["ex_date"])
    return df


# ---------------------------------------------------------------- benchmark
def clean_benchmark(fetched_at: pd.Timestamp, stock_frames: dict) -> tuple[pd.DataFrame, pd.DatetimeIndex]:
    b = read_yahoo(config.BENCHMARK)
    b, iss = C.normalise_index(b, "NIFTY50")
    issues.extend(iss)
    b, iss = C.drop_incomplete_last_row(b, fetched_at, "NIFTY50")
    issues.extend(iss)
    close, iss = C.invalid_prices(b["Close"], "NIFTY50")
    issues.extend(iss)
    close = close[close.index >= START]

    # share of live stocks with a real print on each date (volume > 0 or the close moved);
    # on exchange holidays Yahoo rows, when present, repeat the last close with zero volume
    all_dates = pd.DatetimeIndex(sorted(set().union(*[set(df.index) for df in stock_frames.values()])))
    counts = pd.Series(0.0, index=all_dates)
    alive = pd.Series(0.0, index=all_dates)
    for df in stock_frames.values():
        real = (df["Volume"].fillna(0) > 0) | (df["Close"].diff().abs() > 1e-9)
        counts = counts.add(real.astype(float).reindex(all_dates, fill_value=0.0))
        alive = alive.add(pd.Series(1.0, index=df.index).reindex(all_dates, fill_value=0.0))
    share = (counts / alive.replace(0, np.nan)).fillna(0)
    share = share[share.index >= START]

    # 1) index rows on days with (almost) no fresh stock prints: a non-session, unless NSE's own
    #    bhavcopy shows trading — then Yahoo's stock data for that day is stale and is repaired from NSE
    for d in close.index:
        if d in share.index and share.loc[d] < 0.2:
            b = NB.bhavcopy(d)
            if b is not None and len(b) > 300:
                STALE_MARKET_DAYS.append(d)
                issues.append(C.Issue("ALL", str(d.date()), "E_calendar", "Yahoo stock prices stale for a whole session",
                                      f"only {share.loc[d]:.0%} of stocks have a fresh Yahoo print, but NSE traded {len(b)} EQ symbols",
                                      "kept the session; every stock's close replaced with NSE's official close",
                                      f"NSE bhavcopy {d.date()}"))
            else:
                issues.append(C.Issue("NIFTY50", str(d.date()), "E_calendar", "index row on a non-session day",
                                      f"only {share.loc[d]:.0%} of stocks traded and NSE has no bhavcopy", "dropped"))
                close = close.drop(d)
    # 2) sessions with the market open but no index row → fill from NSE's official index close
    gaps = [d for d in share.index if share.loc[d] >= 0.7 and d not in close.index and d <= close.index[-1]]
    for d in gaps:
        v = NB.nifty50_close(d)
        if v is not None:
            close.loc[d] = v
            issues.append(C.Issue("NIFTY50", str(d.date()), "E_calendar", "missing benchmark day",
                                  f"{share.loc[d]:.0%} of stocks traded but Yahoo has no ^NSEI row",
                                  f"filled with NSE official close {v:,.2f}",
                                  f"NSE ind_close_all_{d:%d%m%Y}.csv"))
        else:
            issues.append(C.Issue("NIFTY50", str(d.date()), "E_calendar", "missing benchmark day",
                                  f"{share.loc[d]:.0%} of stocks traded but Yahoo has no ^NSEI row",
                                  "NSE official file unavailable for this date — left out of the calendar",
                                  "NSE archives"))
    close = close.sort_index()
    iss, _ = C.stale_runs(close, "NIFTY50")
    issues.extend(iss)
    calendar = pd.DatetimeIndex(close.index)

    vix = read_yahoo(config.VIX)
    out = pd.DataFrame({"NIFTY50": close})
    if vix is not None and not vix.empty:
        vix, _ = C.normalise_index(vix, "INDIAVIX")
        v, _ = C.invalid_prices(vix["Close"], "INDIAVIX")
        out["INDIAVIX"] = v.reindex(calendar).ffill(limit=config.MAX_FFILL)
    return out, calendar


# ---------------------------------------------------------------- anchoring
def anchor(sym: str, yraw: pd.Series, chain, checkpoints: list[pd.Timestamp]) -> tuple[pd.Series, list[dict], dict]:
    """Rescale Yahoo's raw series to NSE's official closes, piece by piece."""
    def q_at(d):
        d = pd.Timestamp(d)
        if d not in yraw.index or pd.isna(yraw.loc[d]) or yraw.loc[d] <= 0:
            return None
        v = NB.official_close(nse_symbol_on(sym, d, chain), d)
        return None if v is None or v <= 0 else v / float(yraw.loc[d])

    cps = [d for d in checkpoints if d >= yraw.first_valid_index()]
    q = pd.Series({d: q_at(d) for d in cps}, dtype=float).dropna()
    info = {"checkpoints": len(cps), "matched": int(len(q))}
    if q.empty:
        return yraw, [], info
    changes, outliers = C.find_q_changes(q, ANCHOR_TOL)
    for d in outliers:
        issues.append(C.Issue(sym, str(d.date()), "F_integrity", "single-day disagreement with NSE",
                              f"NSE close ÷ Yahoo close = {q.loc[d]:.4f} on one checkpoint only",
                              "no level change; day kept", f"NSE bhavcopy {d.date()}"))
    cal = list(yraw.index)
    change_dates, rows = [], []
    for a, b in changes:
        between = [d for d in cal if a < d <= b]
        qa, qb = float(q.loc[a]), float(q.loc[b])
        d = C.bisect_change(between, qa, qb, q_at)
        change_dates.append(d)
        rows.append({"ticker": sym, "change_date": str(d.date()), "q_before": round(qa, 6), "q_after": round(qb, 6),
                     "yahoo_hidden_factor": round(qa / qb, 6)})
    # level of each segment = median checkpoint q inside it
    bounds = [yraw.index[0]] + change_dates + [yraw.index[-1] + pd.Timedelta(days=1)]
    levels = []
    for lo, hi in zip(bounds[:-1], bounds[1:]):
        seg = q[(q.index >= lo) & (q.index < hi)]
        lv = float(seg.median()) if len(seg) else 1.0
        levels.append(1.0 if abs(lv - 1) < ANCHOR_TOL / 2 else lv)
    qs = C.piecewise_q(yraw.index, change_dates, levels)
    info.update({"changes": len(change_dates), "levels": [round(x, 4) for x in levels]})
    return yraw * qs, rows, info


# ---------------------------------------------------------------- per stock

SPOS_FROM = pd.Timestamp("2023-04-30")  # NSE Indices' demerger methodology using the special pre-open price
SPOS_URL = "https://www.nseindia.com/products-services/equity-market-special-pre-open-session"


def spos_ratio(sym: str, day: pd.Timestamp, adj: pd.Series, chain) -> tuple[float, str] | None:
    """Official demerger ratio from NSE's special pre-open session (SPOS): the price discovered for the
    parent on the ex-date (bhavcopy OPEN) ÷ its previous close. NSE Indices values the spun-off company
    at exactly this difference (constant price = previous close − SPOS price)."""
    pos = adj.index.get_loc(day)
    prev = adj.index[pos - 1]
    b_ex, b_prev = NB.bhavcopy(day), NB.bhavcopy(prev)
    s_ex, s_prev = nse_symbol_on(sym, day, chain), nse_symbol_on(sym, prev, chain)
    if b_ex is None or b_prev is None or s_ex not in b_ex.index or s_prev not in b_prev.index:
        return None
    o = float(np.atleast_1d(b_ex.loc[s_ex, "OPEN"])[0])
    c = float(np.atleast_1d(b_prev.loc[s_prev, "CLOSE"])[0])
    if not (0 < o < c):
        return None
    f = o / c
    src = (f"NSE special pre-open session price discovery: opening price ₹{o:,.2f} on {day.date()} vs previous close "
           f"₹{c:,.2f} on {prev.date()} (NSE bhavcopies; SPOS framework {SPOS_URL})")
    return f, src


INFERRED_RENAMES: list[dict] = []


def infer_unlisted_rename(sym: str, yraw: pd.Series, chain, checkpoints) -> list:
    """Some old renames are missing from NSE's symbol-change list (e.g. COLGATE → COLPAL in 2007).
    If NSE's bhavcopy does not list the symbol on early checkpoints while Yahoo has prices, look for
    the one symbol with the same first three letters whose official closes move exactly with Yahoo's
    series on three checkpoints, find the switch day by bisection, and accept it only as a clean
    hand-over: the old symbol trades the day before and disappears the day the new one appears.
    (A demerger where the old company lives on under another name, e.g. Bajaj Auto → Bajaj
    Holdings in 2008, fails this test and is handled as a new listing instead.)"""
    first = yraw.first_valid_index()
    cps = [d for d in checkpoints if d >= max(first, START) and d in yraw.index][:60]
    def present(d):
        b = NB.bhavcopy(d)
        return None if b is None else nse_symbol_on(sym, d, chain) in b.index
    absent = [d for d in cps if present(d) is False]
    present_cps = [d for d in cps if present(d)]
    if not absent or not present_cps or absent[0] > present_cps[0]:
        return chain
    prefixes = {s[:3] for s in [sym] + [c[0] for c in chain]}

    # Yahoo's level may carry an unknown scale here, so match price *moves* between checkpoints
    def closes(d):
        b = NB.bhavcopy(d)
        b = b[[s[:3] in prefixes and s != sym for s in b.index]]
        return b["CLOSE"].groupby(level=0).first()
    early = [d for d in absent if d < present_cps[0] and len(closes(d))]
    if len(early) < 3:
        return chain
    e0, e1, e2 = early[0], early[len(early) // 2], early[-1]
    c0, c1, c2 = closes(e0), closes(e1), closes(e2)
    y0, y1, y2 = (float(yraw.loc[d]) for d in (e0, e1, e2))
    hits = set()
    for s in c0.index.intersection(c1.index).intersection(c2.index):
        if abs((c1[s] / c0[s]) / (y1 / y0) - 1) < 0.01 and abs((c2[s] / c0[s]) / (y2 / y0) - 1) < 0.01:
            hits.add(s)
    if len(hits) != 1:
        return chain
    old = hits.pop()
    # first day the new symbol trades
    lo, hi = early[-1], present_cps[0]
    days = [d for d in yraw.index if lo < d <= hi]
    a, b_ = -1, len(days) - 1
    while b_ - a > 1:
        m = (a + b_) // 2
        if present(days[m]):
            b_ = m
        else:
            a = m
    when = days[b_]
    # clean hand-over: the old symbol stops trading within 15 sessions before the new one starts
    # and never trades again afterwards
    def old_listed(d):
        b = NB.bhavcopy(d)
        return b is not None and old in b.index
    if any(old_listed(d) for d in [when] + [c for c in cps if c > when][:3]):
        return chain
    window_days = [d for d in yraw.index if lo <= d < when][-15:]
    if not any(old_listed(d) for d in window_days):
        return chain
    early = [e0, e1, e2]
    INFERRED_RENAMES.append({"current_symbol": sym, "old_symbol": old, "changed_on": str(when.date()),
                             "evidence": f"official closes move exactly with Yahoo's {sym} on {early[0].date()}, {early[len(early) // 2].date()} and {early[-1].date()}"})
    issues.append(C.Issue(sym, str(when.date()), "C_symbol", "symbol change missing from NSE's list",
                          f"NSE bhavcopies list {old}, whose official closes move exactly with Yahoo's {sym} on "
                          f"{early[0].date()}, {early[len(early) // 2].date()} and {early[-1].date()}, until {sym} first appears on {when.date()}",
                          f"treated {old} → {sym} as a rename on {when.date()}", "NSE bhavcopies (price match)"))
    return chain + [(old, when, "(inferred from NSE bhavcopies)")] if not chain else \
        sorted(chain + [(old, when, "(inferred from NSE bhavcopies)")], key=lambda x: x[1], reverse=True)


def trim_before_nse_listing(sym: str, raw: pd.Series, chain, checkpoints) -> pd.Series:
    """Yahoo sometimes carries prices for dates before the company traded on NSE (e.g. a demerged
    company before its listing). Find the first day NSE's bhavcopy lists the symbol and drop
    everything earlier."""
    first = raw.first_valid_index()
    if first is None:
        return raw
    cps = [d for d in checkpoints if d >= max(first, START)]
    def listed(d):
        b = NB.bhavcopy(d)
        if b is None:
            return None
        return nse_symbol_on(sym, d, chain) in b.index
    state = [(d, listed(d)) for d in cps[:60]]
    state = [(d, s) for d, s in state if s is not None]
    if not state or state[0][1]:
        return raw  # listed at the first checkpoint
    present = [d for d, s in state if s]
    if not present:
        return raw
    hi = present[0]
    lo = max(d for d, s in state if not s and d < hi)
    days = [d for d in raw.index if lo < d <= hi]
    a, b = -1, len(days) - 1
    while b - a > 1:
        m = (a + b) // 2
        s = listed(days[m])
        if s is None or not s:
            a = m
        else:
            b = m
    start = days[b]
    out = raw.copy()
    out.loc[:start - pd.Timedelta(days=1)] = np.nan
    issues.append(C.Issue(sym, str(start.date()), "C_symbol", "Yahoo history before NSE listing",
                          f"Yahoo has prices from {first.date()}, but NSE's bhavcopy first lists {nse_symbol_on(sym, start, chain)} on {start.date()}",
                          f"dropped Yahoo rows before {start.date()}", "NSE bhavcopies"))
    return out


def repair_or_trim_stale(sym: str, raw: pd.Series, chain) -> tuple[pd.Series, pd.Timestamp | None]:
    """Runs of more than STALE_EXCLUDE_DAYS identical closes. If NSE shows the stock trading at other
    prices inside the run, Yahoo's data is wrong: replace every day of the run with NSE's official close.
    If NSE has no trades, it was a real suspension: the stock's usable history starts after the run."""
    s = raw[raw.index >= START - pd.Timedelta(days=10)]
    same = s.eq(s.shift())
    run_id = (~same).cumsum()
    out, trimmed = raw.copy(), None
    for _, grp in s.groupby(run_id):
        if len(grp) <= config.STALE_EXCLUDE_DAYS:
            continue
        mid = grp.index[len(grp) // 2]
        v = NB.official_close(nse_symbol_on(sym, mid, chain), mid)
        if v is not None and abs(v / float(grp.iloc[0]) - 1) > 0.005:
            fixed, missing = 0, 0
            for d in grp.index[1:]:
                x = NB.official_close(nse_symbol_on(sym, d, chain), d)
                if x is None:
                    out.loc[d] = np.nan
                    missing += 1
                else:
                    out.loc[d] = x
                    fixed += 1
            issues.append(C.Issue(sym, str(grp.index[0].date()), "E_calendar", "stale prices are a Yahoo data error",
                                  f"{len(grp)} identical Yahoo closes of {grp.iloc[0]:.2f} ({grp.index[0].date()} → {grp.index[-1].date()}); "
                                  f"NSE shows the stock trading at ₹{v:,.2f} on {mid.date()}",
                                  f"replaced {fixed} day(s) with NSE official closes" + (f"; {missing} without an NSE price left missing" if missing else ""),
                                  "NSE bhavcopies"))
        else:
            trimmed = grp.index[-1]
            out.loc[:trimmed] = np.nan
            issues.append(C.Issue(sym, str(grp.index[0].date()), "E_calendar", "suspension / relisting gap",
                                  f"{len(grp)} identical closes ({grp.index[0].date()} → {grp.index[-1].date()}); "
                                  f"NSE shows no trades on {mid.date()}",
                                  f"usable history starts after {trimmed.date()} (fails the continuous-history rule)",
                                  "NSE bhavcopies"))
    return out, trimmed

def clean_stock(sym: str, meta_row: pd.Series, calendar: pd.DatetimeIndex, nifty_ret: pd.Series,
                fetched_at: pd.Timestamp, changes_tbl: pd.DataFrame, checkpoints, demerger_ratios: pd.DataFrame):
    t = f"{sym}.NS"
    out = {"symbol": sym, "status": "excluded", "reason": "", "ca_rows": [], "anchor_rows": [],
           "excluded_returns": [], "adj_gap": None}
    df = read_yahoo(t)
    if df is None or df.empty:
        out["reason"] = "no Yahoo Finance data"
        issues.append(C.Issue(sym, "", "E_calendar", "no data", "Yahoo returned nothing", "excluded", "yfinance"))
        return None, out, None
    chain = symbol_chain(sym, changes_tbl)

    # E: calendar hygiene
    df, iss = C.normalise_index(df, sym); issues.extend(iss)
    df, iss = C.drop_incomplete_last_row(df, fetched_at, sym); issues.extend(iss)
    df, iss = C.drop_non_sessions(df, calendar.union(df.index[df.index < START]), sym); issues.extend(iss)

    # D: invalid prints
    close, iss = C.invalid_prices(df["Close"], sym); issues.extend(iss)
    splits = df["Stock Splits"].fillna(0)

    # A: Yahoo raw → anchored to NSE official closes
    yraw = C.reconstruct_raw(close, splits)
    chain = infer_unlisted_rename(sym, yraw, chain, checkpoints)
    true_raw, anchor_rows, ainfo = anchor(sym, yraw, chain, checkpoints)
    out["anchor_rows"] = anchor_rows
    nse = load_nse_ca(sym, chain)
    for r in anchor_rows:
        d = pd.Timestamp(r["change_date"])
        near = nse[(nse["ex_date"] - d).abs() <= pd.Timedelta(days=7)]
        what = "; ".join(near["subject"].tolist()) or "no NSE corporate action within ±7 days"
        issues.append(C.Issue(sym, r["change_date"], "A_split_bonus", "Yahoo price level inconsistent with NSE",
                              f"NSE close ÷ Yahoo close steps from {r['q_before']:.4f} to {r['q_after']:.4f} "
                              f"(Yahoo applied an unrecorded factor {r['yahoo_hidden_factor']:.4f} to earlier prices). NSE actions: {what}",
                              "rescaled Yahoo's history to NSE's official closes; adjustment rebuilt from NSE actions below",
                              f"NSE bhavcopies (bisection to {r['change_date']})"))

    # E: sessions where Yahoo's prices are stale market-wide → NSE official close
    for d in STALE_MARKET_DAYS:
        if d in true_raw.index:
            v = NB.official_close(nse_symbol_on(sym, d, chain), d)
            true_raw.loc[d] = v if v is not None else np.nan

    # C/E: Yahoo rows from before the stock traded on NSE under this (or an earlier) symbol
    true_raw = trim_before_nse_listing(sym, true_raw, chain, checkpoints)

    # E: long stale runs — Yahoo error (repair from NSE) or genuine suspension (start after it)
    true_raw, trimmed_to = repair_or_trim_stale(sym, true_raw, chain)

    # A: splits and bonuses from NSE, confirmed in the official-level prices
    ratio = true_raw / true_raw.shift(1)
    events: list[tuple[pd.Timestamp, float]] = []
    explained: dict = {}
    action_dates = set()
    comb = C.combined_factors(nse)
    yahoo_ev = splits[splits > 0]
    for _, a in comb.iterrows():
        ex = pd.Timestamp(a["ex_date"])
        if ex <= true_raw.index[0] or ex > true_raw.index[-1]:
            continue
        day = true_raw.index[true_raw.index >= ex][0]
        obs = float(ratio.loc[day]) if pd.notna(ratio.loc[day]) else np.nan
        f = float(a["factor"])
        yhit = yahoo_ev[(yahoo_ev.index >= ex - pd.Timedelta(days=7)) & (yahoo_ev.index <= ex + pd.Timedelta(days=7))]
        ytxt = (f"Yahoo recorded {'; '.join(f'{v:g}-for-1 on {k.date()}' for k, v in yhit.items())}"
                if len(yhit) else "Yahoo has no record")
        # visible = the day's price ratio sits closer (in log terms) to the action's factor than to "no change"
        confirmed = pd.notna(obs) and obs > 0 and abs(np.log(obs / f)) < abs(np.log(obs))
        row = {"ticker": sym, "ex_date": str(ex.date()), "applied_on": str(day.date()), "type": "split/bonus",
               "nse_subject": a["subject"], "price_factor": round(f, 6),
               "observed_price_ratio": round(obs, 4) if pd.notna(obs) else None,
               "yahoo_record": ytxt, "applied": bool(confirmed),
               "source": f"NSE corporate actions ({a['subject']}, ex-date {ex.date()}); price move confirmed in NSE-anchored closes"}
        if ex < START:
            if confirmed:
                events.append((day, f))
            continue  # before the analysis window: applied silently, not reported
        if confirmed:
            events.append((day, f))
            explained[day] = f"corporate action: {a['subject']} (factor {f:.4f})"
            action_dates.add(day)
            if len(yhit) and abs(1 / float(yhit.iloc[0]) / f - 1) > config.SPLIT_TOLERANCE:
                issues.append(C.Issue(sym, str(ex.date()), "A_split_bonus", "Yahoo split ratio differs from NSE",
                                      f"Yahoo {float(yhit.iloc[0]):g}-for-1 vs NSE price factor {f:.4f}",
                                      "used NSE's ratio", "NSE corporate actions; yfinance action history"))
            elif len(yhit) and yhit.index[0] != day:
                issues.append(C.Issue(sym, str(ex.date()), "A_split_bonus", "wrong ex-date in Yahoo",
                                      f"Yahoo dated it {yhit.index[0].date()}, NSE ex-date {ex.date()}; the price moved on {day.date()}",
                                      "applied on the NSE ex-date", "NSE corporate actions; yfinance action history"))
            elif not len(yhit):
                issues.append(C.Issue(sym, str(ex.date()), "A_split_bonus", "split/bonus missing from Yahoo's action history",
                                      f"{a['subject']}; price ratio {obs:.4f} on {day.date()} vs factor {f:.4f}",
                                      "added to data/corporate_actions.csv and applied", f"NSE corporate actions ({a['subject']})"))
            else:
                issues.append(C.Issue(sym, str(ex.date()), "A_split_bonus", "split/bonus verified",
                                      f"{a['subject']}; Yahoo {float(yhit.iloc[0]):g}-for-1; price ratio {obs:.4f}",
                                      "applied", "NSE corporate actions; yfinance action history"))
        else:
            issues.append(C.Issue(sym, str(ex.date()), "A_split_bonus", "NSE action not visible in prices",
                                  f"{a['subject']}: expected price ratio {f:.4f}, observed {obs:.4f} on {day.date()}",
                                  "not applied — flagged for review", f"NSE corporate actions ({a['subject']})"))
        out["ca_rows"].append(row)
    adj = C.apply_factors(true_raw, events)

    # B: demergers and capital reductions
    for _, a in nse[nse["kind"].isin(["demerger", "capital_reduction"])].iterrows():
        ex = pd.Timestamp(a["ex_date"])
        if ex < START or ex > adj.index[-1]:
            continue
        day, r = C.demerger_drop(adj, ex)
        if day is None or r is None:
            continue
        mkt = float(nifty_ret.get(day, 0.0))
        rel = r - 1 - mkt
        hit = demerger_ratios[(demerger_ratios["ticker"] == sym) &
                              ((demerger_ratios["ex_date"] - ex).abs() <= pd.Timedelta(days=7))]
        spos = spos_ratio(sym, day, adj, chain) if (len(hit) == 0 and day >= SPOS_FROM and rel < DEMERGER_REL_DROP) else None
        row = {"ticker": sym, "ex_date": str(ex.date()), "applied_on": str(day.date()), "type": a["kind"],
               "nse_subject": a["subject"], "observed_price_ratio": round(r, 4), "yahoo_record": "",
               "price_factor": None, "applied": False, "source": ""}
        if len(hit) or spos:
            if len(hit):
                f, src = float(hit["factor"].iloc[0]), f"{hit['basis'].iloc[0]} — {hit['source'].iloc[0]}"
            else:
                f, src = spos
            adj = C.apply_factors(adj, [(day, f)])
            events.append((day, f))
            row.update(price_factor=round(f, 6), applied=True, source=src)
            explained[day] = f"demerger adjusted with the official ratio {f:.4f}"
            issues.append(C.Issue(sym, str(ex.date()), "B_demerger", f"{a['kind']} adjusted with official ratio",
                                  f"one-day price ratio {r:.4f} (Nifty 50 {mkt:+.1%}); official factor {f:.4f}",
                                  "pre-event history multiplied by the official factor", src))
        elif rel < DEMERGER_REL_DROP:
            adj, f = C.neutralise_day(adj, day)
            out["excluded_returns"].append({"ticker": sym, "date": str(day.date()),
                                            "reason": f"{a['kind']} ex-date ({a['subject']}); no verified official ratio"})
            row.update(price_factor=round(f, 6), applied=True,
                       source="no verified official ratio — that day's return dropped (treated as missing)")
            explained[day] = f"{a['kind']} day — return treated as missing"
            issues.append(C.Issue(sym, str(ex.date()), "B_demerger", f"{a['kind']}: no official ratio found",
                                  f"one-day price ratio {r:.4f}, {rel:+.1%} vs Nifty 50",
                                  "dropped that single day's return (missing, not a loss)", f"NSE corporate actions ({a['subject']})"))
        else:
            row.update(source="NSE lists the action; price shows no unusual fall — no adjustment needed")
            issues.append(C.Issue(sym, str(ex.date()), f"B_demerger", f"{a['kind']}: no price impact",
                                  f"one-day price ratio {r:.4f} ({rel:+.1%} vs Nifty 50)", "no adjustment",
                                  f"NSE corporate actions ({a['subject']})"))
        action_dates.add(day)
        out["ca_rows"].append(row)

    # A: rights issues (Yahoo does not adjust them): theoretical ex-rights price from NSE's terms
    for _, a in nse[nse["kind"] == "rights"].iterrows():
        ex = pd.Timestamp(a["ex_date"])
        if ex < START or ex > adj.index[-1]:
            continue
        terms = C.rights_terms(a["subject"])
        fv = a.get("face_value")
        idx = true_raw.index[true_raw.index >= ex]
        if terms is None or pd.isna(fv) or not len(idx):
            continue
        day = idx[0]
        pos = true_raw.index.get_loc(day)
        cum = float(true_raw.iloc[pos - 1])
        nr, held, prem = terms
        subs = float(fv) + prem
        f = C.rights_factor(nr, held, subs, cum)
        row = {"ticker": sym, "ex_date": str(ex.date()), "applied_on": str(day.date()), "type": "rights",
               "nse_subject": a["subject"], "observed_price_ratio": round(float(true_raw.iloc[pos] / cum), 4),
               "yahoo_record": "Yahoo does not adjust rights issues", "price_factor": None, "applied": False,
               "source": ""}
        if f is None:
            row["source"] = f"NSE corporate actions; subscription ₹{subs:,.2f} ≥ cum-rights price ₹{cum:,.2f} — no adjustment"
        else:
            adj = C.apply_factors(adj, [(day, f)])
            events.append((day, f))
            action_dates.add(day)
            explained[day] = f"rights issue {nr}:{held} at ₹{subs:,.2f} adjusted (factor {f:.4f})"
            row.update(price_factor=round(f, 6), applied=True,
                       source=(f"NSE corporate actions ({a['subject']}, face value ₹{float(fv):g}): theoretical ex-rights price "
                               f"= ({held}×₹{cum:,.2f} + {nr}×₹{subs:,.2f}) ÷ {nr + held}"))
            issues.append(C.Issue(sym, str(ex.date()), "A_split_bonus", "rights issue adjusted",
                                  f"{a['subject']}; cum-rights close ₹{cum:,.2f}; subscription ₹{subs:,.2f}; factor {f:.4f}",
                                  "pre-event history multiplied by the theoretical ex-rights factor", f"NSE corporate actions ({a['subject']})"))
        out["ca_rows"].append(row)

    # A: residual split-like jumps — verify against Yahoo's action history, else a genuine move
    for d, v, k in C.detect_split_jumps(adj[adj.index >= START]):
        if d in action_dates:
            continue
        mkt = float(nifty_ret.get(d, 0.0))
        yhit = yahoo_ev[(yahoo_ev.index >= d - pd.Timedelta(days=3)) & (yahoo_ev.index <= d + pd.Timedelta(days=3))]
        yf_ok = len(yhit) and abs(np.log(v * float(yhit.iloc[0]))) < abs(np.log(v))
        if yf_ok:
            f = 1 / float(yhit.iloc[0])
            adj = C.apply_factors(adj, [(d, f)])
            events.append((d, f))
            action_dates.add(d)
            explained[d] = f"split {float(yhit.iloc[0]):g}-for-1 (yfinance action history)"
            out["ca_rows"].append({"ticker": sym, "ex_date": str(d.date()), "applied_on": str(d.date()), "type": "split/bonus",
                                   "nse_subject": "(no NSE record)", "price_factor": round(f, 6),
                                   "observed_price_ratio": round(v, 4),
                                   "yahoo_record": f"Yahoo recorded {float(yhit.iloc[0]):g}-for-1 on {yhit.index[0].date()}",
                                   "applied": True, "source": "yfinance action history (NSE corporate-actions feed has no record)"})
            issues.append(C.Issue(sym, str(d.date()), "A_split_bonus", "split missing from NSE feed, found in Yahoo",
                                  f"price ratio {v:.4f}; Yahoo {float(yhit.iloc[0]):g}-for-1 on {yhit.index[0].date()}",
                                  "applied (source: yfinance action history)", "yfinance action history"))
        else:
            issues.append(C.Issue(sym, str(d.date()), "A_split_bonus", "split-like move with no corporate action",
                                  f"price ratio {v:.4f} ≈ {config.SPLIT_RATIOS[k]} (Nifty 50 {mkt:+.1%} that day); "
                                  f"no split/bonus in NSE or Yahoo records within ±7 days",
                                  "kept as a genuine move", "NSE corporate actions; yfinance action history"))
            explained[d] = (f"genuine move: ratio {v:.4f} resembles a split ratio but neither NSE nor Yahoo records "
                            f"any action; Nifty 50 {mkt:+.1%} that day")

    # A: double-adjustment check after all adjustments
    for d, v, prob in C.check_double_adjustment(adj, events):
        issues.append(C.Issue(sym, str(d.date()), "A_split_bonus", "adjustment check failed",
                              f"price ratio {v:.4f} {prob}", "flagged for review", "price data"))

    # D: bad prints on the adjusted series
    adj, iss = C.decimal_errors(adj, sym); issues.extend(iss)
    def nse_confirms(d):
        v = NB.official_close(nse_symbol_on(sym, d, chain), d)
        return v is not None and pd.notna(true_raw.get(d)) and abs(v / float(true_raw.loc[d]) - 1) <= 0.01
    adj, iss = C.spike_and_revert(adj, sym, action_dates, confirm=nse_confirms); issues.extend(iss)

    # A: dividends (NSE official amounts, raw ₹ per share on the day)
    divs = C.nse_dividends(nse)
    div_src = "NSE corporate actions"
    if divs.empty:
        dv = df["Dividends"].fillna(0)
        divs = (dv[dv > 0] * (true_raw / close).reindex(dv[dv > 0].index)).dropna()
        div_src = "yfinance action history"
    div_days = pd.Series(0.0, index=adj.index)
    for ex, amt in divs.items():
        idx = adj.index[adj.index >= ex]
        if len(idx):
            div_days.loc[idx[0]] += float(amt)
    # dividend yield must be computed on the raw price of the day before
    prev_raw = true_raw.shift(1)
    yld = (div_days / prev_raw).where(div_days > 0)
    for d, y in yld.dropna().items():
        if y > 0.15:
            issues.append(C.Issue(sym, str(d.date()), "A_split_bonus", "large dividend",
                                  f"₹{div_days.loc[d]:.2f} = {y:.0%} of the previous close", "kept (official NSE record); flagged",
                                  div_src))
    factor = pd.Series(1.0, index=adj.index)
    for d, y in yld.dropna().items():
        if 0 < y < 0.5:
            factor[factor.index < d] *= 1 - y
    total = adj * factor

    # A: compare with Yahoo's Adj Close
    gap = C.compare_adjclose(total[total.index >= START], df["Adj Close"][df.index >= START])
    if len(gap):
        mx = float(gap.abs().max())
        out["adj_gap"] = mx
        if mx > config.ADJ_MISMATCH_TOL:
            worst = gap.abs().idxmax()
            why = []
            if anchor_rows:
                why.append(f"{len(anchor_rows)} Yahoo level error(s) corrected against NSE")
            if any(r.get("applied") and r["type"] != "split/bonus" for r in out["ca_rows"]):
                why.append("demerger handled differently from Yahoo")
            if div_src.startswith("NSE"):
                why.append("dividends from NSE records rather than Yahoo's")
            issues.append(C.Issue(sym, str(worst.date()), "A_split_bonus", "Adj Close differs from Yahoo by > 0.5%",
                                  f"max gap {mx:.2%} on {worst.date()}", "kept our rebuild — " + ("; ".join(why) or "dividend timing / rounding differences"),
                                  "yfinance Adj Close vs our rebuild"))

    # E: align to the Nifty 50 calendar from HISTORY_START
    total = total[total.index >= START]
    aligned, iss, keep_gaps = C.align_to_calendar(total, calendar, sym)
    issues.extend(iss)
    iss, keep_stale = C.stale_runs(total, sym)
    issues.extend(iss)

    # D: every remaining move beyond ±20% explained
    for i in C.flag_large_moves(aligned, sym, explained):
        d = pd.Timestamp(i.date)
        if "genuine" in i.action:
            i.action = (f"kept — genuine move: no corporate action within ±3 days, did not revert; "
                        f"Nifty 50 {nifty_ret.get(d, 0.0):+.1%} that day")
        issues.append(i)

    first = aligned.first_valid_index()
    n_days = int(aligned.notna().sum())
    if not keep_gaps:
        out["reason"] = "more than 2% of trading days missing"
    elif not keep_stale:
        out["reason"] = "stale-price run longer than 10 days (suspension)"
    elif first is None:
        out["reason"] = "no prices after HISTORY_START"
    elif first <= calendar[0]:
        out["status"] = "core"
    elif n_days >= MIN_EXTENDED_DAYS:
        out["status"] = "extended"
        out["reason"] = f"history starts {first.date()} — usable for custom picks; events before it are greyed out"
    else:
        out["reason"] = f"history starts {first.date()} — under 3 years, too short for the risk label"
    out.update({"first_date": str(first.date()) if first is not None else "", "n_days": n_days,
                "anchor": ainfo, "dividend_source": div_src})
    return aligned, out, true_raw


# ---------------------------------------------------------------- spot checks
def spot_checks(prices_raw: dict, calendar, changes_tbl, n: int = 24, seed: int = config.SEED) -> pd.DataFrame:
    rng = random.Random(seed)
    syms = sorted(prices_raw)
    rows = []
    tries = 0
    while len(rows) < n and tries < n * 6:
        tries += 1
        s = rng.choice(syms)
        ser = prices_raw[s].dropna()
        ser = ser[ser.index >= START]
        d = rng.choice(list(ser.index))
        chain = symbol_chain(s, changes_tbl)
        v = NB.official_close(nse_symbol_on(s, d, chain), d)
        if v is None:
            continue
        ours = float(ser.loc[d])
        rows.append({"ticker": s, "date": str(d.date()), "nse_close": v, "snapshot_raw_close": round(ours, 2),
                     "difference": round(ours / v - 1, 5), "within_1pct": abs(ours / v - 1) <= 0.01,
                     "source": f"NSE bhavcopy {d.date()}"})
    # benchmark spot checks
    k = 0
    while k < 6 and tries < n * 10:
        tries += 1
        d = rng.choice(list(calendar[calendar >= pd.Timestamp("2012-06-01")]))
        v = NB.nifty50_close(d)
        if v is None:
            continue
        ours = float(prices_raw["__NIFTY50__"].loc[d])
        rows.append({"ticker": "NIFTY50", "date": str(d.date()), "nse_close": v, "snapshot_raw_close": round(ours, 2),
                     "difference": round(ours / v - 1, 5), "within_1pct": abs(ours / v - 1) <= 0.01,
                     "source": f"NSE ind_close_all_{d:%d%m%Y}.csv"})
        k += 1
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- main
def main() -> None:
    log_meta = json.loads((RAW / "fetch_log.json").read_text()) if (RAW / "fetch_log.json").exists() else {}
    fetched_at = pd.Timestamp(log_meta.get("fetched_at", datetime.now().isoformat()))
    n200 = pd.read_csv(RAW / "nse" / "nifty200.csv")
    n100 = set(pd.read_csv(RAW / "nse" / "nifty100.csv")["Symbol"].astype(str).str.strip())
    n200["Symbol"] = n200["Symbol"].astype(str).str.strip()
    changes_tbl = load_symbol_changes()
    demerger_ratios = load_demerger_ratios()

    log("Loading raw stock files …")
    frames = {}
    for s in n200["Symbol"]:
        df = read_yahoo(f"{s}.NS")
        if df is not None:
            df, _ = C.normalise_index(df, s)
            frames[s] = df
    log(f"  {len(frames)} of {len(n200)} constituents have Yahoo data")

    log("Benchmark …")
    bench, calendar = clean_benchmark(fetched_at, frames)
    nifty_ret = bench["NIFTY50"].pct_change()
    log(f"  calendar {calendar[0].date()} → {calendar[-1].date()}, {len(calendar)} sessions")
    checkpoints = sorted(pd.Series(calendar, index=calendar).groupby([calendar.year, calendar.month]).first().tolist())
    checkpoints.append(calendar[-1])

    cleaned, rows, ca_rows, anchor_rows, excl_rows, raw_for_spot = {}, [], [], [], [], {}
    for i, r in n200.iterrows():
        s = r["Symbol"]
        series, info, true_raw = clean_stock(s, r, calendar, nifty_ret, fetched_at, changes_tbl, checkpoints, demerger_ratios)
        ca_rows += info["ca_rows"]
        anchor_rows += info["anchor_rows"]
        excl_rows += info["excluded_returns"]
        rows.append({"symbol": s, "company": r["Company Name"], "industry": r["Industry"],
                     "cap_bucket": "Large cap" if s in n100 else "Mid cap", "isin": r["ISIN Code"],
                     "status": info["status"], "first_date": info.get("first_date", ""), "n_days": info.get("n_days", 0),
                     "reason": info["reason"], "adj_close_max_gap": None if info["adj_gap"] is None else round(info["adj_gap"], 5),
                     "nse_anchor_matched": (info.get("anchor") or {}).get("matched"),
                     "yahoo_level_fixes": (info.get("anchor") or {}).get("changes", 0),
                     "dividend_source": info.get("dividend_source", "")})
        if series is not None and info["status"] in ("core", "extended"):
            cleaned[s] = series
            raw_for_spot[s] = true_raw
        log(f"  [{i + 1:3d}/{len(n200)}] {s:12s} {info['status']:8s} {info['reason'][:70]}")

    universe = pd.DataFrame(rows)
    prices = pd.DataFrame(cleaned).reindex(calendar)
    prices.index.name = "Date"
    bench.index.name = "Date"

    log("Spot-checking against NSE bhavcopies …")
    raw_for_spot["__NIFTY50__"] = bench["NIFTY50"]
    spots = spot_checks(raw_for_spot, calendar, changes_tbl)
    spots.to_csv(DATA / "spot_checks.csv", index=False)
    log(f"  {len(spots)} spot checks, {int(spots['within_1pct'].sum())} within 1%")

    # integrity: diff vs previous snapshot
    snap = DATA / "prices.csv.gz"
    restated = pd.DataFrame()
    if snap.exists():
        old = pd.read_csv(snap, index_col="Date", parse_dates=["Date"])
        restated = C.diff_snapshots(old, prices.round(6))
        restated.to_csv(DATA / "restatements_vs_previous_snapshot.csv", index=False)
        for _, x in restated.head(200).iterrows():
            issues.append(C.Issue(x["ticker"], str(pd.Timestamp(x["date"]).date()), "F_integrity",
                                  "historical price restated since the last snapshot",
                                  f"changed by {x['relative_change']:.2%}", "new value kept; review", "snapshot diff"))

    prices.to_csv(snap, float_format="%.6g", compression={"method": "gzip", "mtime": 0})
    bench.to_csv(DATA / "benchmark.csv.gz", float_format="%.6g", compression={"method": "gzip", "mtime": 0})
    universe.to_csv(DATA / "universe.csv", index=False)
    pd.DataFrame(ca_rows).to_csv(DATA / "corporate_actions.csv", index=False)
    pd.DataFrame(anchor_rows, columns=["ticker", "change_date", "q_before", "q_after", "yahoo_hidden_factor"]).to_csv(
        DATA / "nse_anchor.csv", index=False)
    pd.DataFrame(excl_rows, columns=["ticker", "date", "reason"]).to_csv(DATA / "excluded_returns.csv", index=False)

    # symbol changes relevant to the universe
    sc = []
    for s in n200["Symbol"]:
        for old, when, comp in symbol_chain(s, changes_tbl):
            sc.append({"current_symbol": s, "old_symbol": old, "changed_on": str(when.date()), "company": comp,
                       "source": "NSE symbol-change list (archives.nseindia.com/content/equities/symbolchange.csv)",
                       "history_handling": "Yahoo carries the full history under the new symbol; NSE checks use the old symbol before the change date"})
    for x in INFERRED_RENAMES:
        sc.append({"current_symbol": x["current_symbol"], "old_symbol": x["old_symbol"], "changed_on": x["changed_on"],
                   "company": "", "source": f"NSE bhavcopies — {x['evidence']} (not in NSE's symbol-change list)",
                   "history_handling": "Yahoo carries the full history under the new symbol; NSE checks use the old symbol before the change date"})
    pd.DataFrame(sc).to_csv(DATA / "symbol_changes.csv", index=False)

    rep = C.issues_frame(issues)
    rep.to_csv(DATA / "data_quality_report.csv", index=False)

    meta = {
        "as_of": str(calendar[-1].date()),
        "history_start": str(calendar[0].date()),
        "benchmark_first_date": str(bench["NIFTY50"].first_valid_index().date()),
        "fetched_at": str(fetched_at),
        "n_constituents": int(len(n200)),
        "n_core": int((universe["status"] == "core").sum()),
        "n_extended": int((universe["status"] == "extended").sum()),
        "n_excluded": int((universe["status"] == "excluded").sum()),
        "sessions": int(len(calendar)),
        "prices_sha256": C.checksum_frame(prices),
        "benchmark_sha256": C.checksum_frame(bench),
        "sources": {
            "prices": "Yahoo Finance via yfinance (auto_adjust=False), anchored to NSE bhavcopies",
            "universe": "NSE Nifty 200 / Nifty 100 constituent lists (archives.nseindia.com)",
            "corporate_actions": "NSE corporate-actions API; yfinance action history",
        },
        "restated_prices_vs_previous": int(len(restated)),
    }
    (DATA / "metadata.json").write_text(json.dumps(meta, indent=1))

    # summary
    log("\nSUMMARY")
    log(f"  constituents {len(n200)} | core {meta['n_core']} | extended {meta['n_extended']} | excluded {meta['n_excluded']}")
    log(rep.groupby(["category", "issue"]).size().to_string())
    import quality_doc
    quality_doc.main()


if __name__ == "__main__":
    main()
