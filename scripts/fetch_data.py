"""Download everything the project needs, once, into data/raw/ (gitignored).

Sources
* NSE archives: Nifty 200 and Nifty 100 constituent lists (with NSE's Industry field),
  and the NSE symbol-change list.
* Yahoo Finance via yfinance: raw daily prices (auto_adjust=False → Close and Adj Close)
  with the dividend and split history, for every constituent, ^NSEI and ^INDIAVIX.
* NSE corporate-actions API: every corporate action per symbol since 2007, used to
  confirm (or reject) splits, bonuses and demergers found in the price data.

Run:  python scripts/fetch_data.py            (skips files already cached)
      python scripts/fetch_data.py --refresh  (re-downloads everything)
Last-resort fallback: put one CSV per ticker in data/manual_csv/<SYMBOL>.csv
(columns Date, Close, Adj Close) and re-run; the script tells you which are missing.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config  # noqa: E402

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
NSE_ARCHIVE = "https://archives.nseindia.com/content"
URLS = {
    "nifty200": f"{NSE_ARCHIVE}/indices/ind_nifty200list.csv",
    "nifty100": f"{NSE_ARCHIVE}/indices/ind_nifty100list.csv",
    "symbolchange": f"{NSE_ARCHIVE}/equities/symbolchange.csv",
}
NSE_CA_API = (
    "https://www.nseindia.com/api/corporates-corporateActions?index=equities"
    "&symbol={symbol}&from_date=01-01-2007&to_date={to}"
)

RAW = config.RAW_DIR
YF_DIR = RAW / "yahoo"
CA_DIR = RAW / "nse_ca"
NSE_DIR = RAW / "nse"
FETCH_START = "2007-01-01"  # a little before HISTORY_START so the first return exists


def get_with_retry(session: requests.Session, url: str, tries: int = 5, **kw) -> requests.Response:
    """GET with exponential back-off (1, 2, 4, 8 … seconds)."""
    last = None
    for i in range(tries):
        try:
            r = session.get(url, timeout=30, **kw)
            if r.status_code == 200 and r.content:
                return r
            last = f"HTTP {r.status_code}"
        except requests.RequestException as e:  # network hiccup
            last = repr(e)
        time.sleep(2**i)
    raise RuntimeError(f"failed after {tries} tries: {url} ({last})")


def nse_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9",
                      "Referer": "https://www.nseindia.com/"})
    try:  # cookies help; the API usually works without them too
        s.get("https://www.nseindia.com/", timeout=15)
    except requests.RequestException:
        pass
    return s


def fetch_nse_lists(refresh: bool) -> None:
    NSE_DIR.mkdir(parents=True, exist_ok=True)
    s = nse_session()
    for name, url in URLS.items():
        out = NSE_DIR / f"{name}.csv"
        if out.exists() and not refresh:
            continue
        r = get_with_retry(s, url)
        out.write_bytes(r.content)
        print(f"  saved {out.relative_to(config.ROOT)} ({len(r.content):,} bytes)")
    # keep dated copies of the constituent lists in the repo for traceability
    for name in ("nifty200", "nifty100"):
        df = pd.read_csv(NSE_DIR / f"{name}.csv")
        df.to_csv(config.DATA_DIR / f"nse_{name}_list.csv", index=False)


def _yf_one(ticker: str, end: str) -> pd.DataFrame:
    import yfinance as yf

    h = yf.Ticker(ticker).history(start=FETCH_START, end=end, auto_adjust=False,
                                  actions=True, repair=False)
    if h is None or h.empty:
        return pd.DataFrame()
    h.index = pd.to_datetime(h.index).tz_localize(None).normalize()
    cols = [c for c in ["Open", "High", "Low", "Close", "Adj Close", "Volume",
                        "Dividends", "Stock Splits"] if c in h.columns]
    return h[cols]


def fetch_yahoo(tickers: list[str], refresh: bool, end: str) -> list[str]:
    """Download raw prices + actions per ticker with retries. Returns failures."""
    YF_DIR.mkdir(parents=True, exist_ok=True)
    failed = []
    for i, t in enumerate(tickers, 1):
        out = YF_DIR / f"{t}.csv"
        if out.exists() and not refresh:
            continue
        df = pd.DataFrame()
        for attempt in range(5):
            try:
                df = _yf_one(t, end)
                if not df.empty:
                    break
            except Exception as e:  # yfinance raises many types on rate limits
                print(f"    {t}: attempt {attempt + 1} failed: {e!r}")
            time.sleep(2**attempt)
        if df.empty:
            failed.append(t)
            print(f"  [{i}/{len(tickers)}] {t}: FAILED")
            continue
        df.to_csv(out, index_label="Date")
        print(f"  [{i}/{len(tickers)}] {t}: {len(df):,} rows {df.index[0].date()} → {df.index[-1].date()}")
        time.sleep(0.4)
    return failed


def fetch_nse_actions(symbols: list[str], refresh: bool) -> list[str]:
    CA_DIR.mkdir(parents=True, exist_ok=True)
    s = nse_session()
    to = date.today().strftime("%d-%m-%Y")
    failed = []
    for sym in symbols:
        out = CA_DIR / f"{sym}.json"
        if out.exists() and not refresh:
            continue
        try:
            r = get_with_retry(s, NSE_CA_API.format(symbol=requests.utils.quote(sym), to=to), tries=4)
            data = r.json()
            out.write_text(json.dumps(data, indent=0))
        except Exception as e:
            failed.append(sym)
            print(f"  NSE corporate actions {sym}: FAILED ({e})")
        time.sleep(0.35)
    return failed


def previous_symbols(symbol: str, changes: pd.DataFrame) -> list[tuple[str, str]]:
    """Walk NSE's symbol-change list backwards: [(old_symbol, change_date), …], newest first."""
    chain, cur, seen = [], symbol, set()
    while cur not in seen:
        seen.add(cur)
        hit = changes[changes["new"] == cur]
        if hit.empty:
            break
        row = hit.sort_values("date").iloc[-1]
        chain.append((row["old"], row["date"].strftime("%Y-%m-%d")))
        cur = row["old"]
    return chain


def load_symbol_changes() -> pd.DataFrame:
    raw = pd.read_csv(NSE_DIR / "symbolchange.csv", header=None, encoding="latin-1",
                      names=["company", "old", "new", "date"], skiprows=1)
    raw = raw.dropna(subset=["old", "new"])
    raw["old"] = raw["old"].astype(str).str.strip()
    raw["new"] = raw["new"].astype(str).str.strip()
    raw["date"] = pd.to_datetime(raw["date"].astype(str).str.strip(), format="%d-%b-%Y", errors="coerce")
    return raw.dropna(subset=["date"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    end = (pd.Timestamp(date.today()) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

    print("1/5 NSE constituent and symbol-change lists")
    fetch_nse_lists(args.refresh)
    n200 = pd.read_csv(NSE_DIR / "nifty200.csv")
    symbols = n200["Symbol"].astype(str).str.strip().tolist()
    print(f"  Nifty 200: {len(symbols)} symbols")

    print("2/5 Yahoo Finance: benchmark and India VIX")
    fails = fetch_yahoo([config.BENCHMARK, config.VIX], args.refresh, end)
    if config.BENCHMARK in fails:
        sys.exit("Benchmark download failed — stop (no fabricated data).")

    print("3/5 Yahoo Finance: constituents (raw Close, Adj Close, dividends, splits)")
    fails = fetch_yahoo([f"{s}.NS" for s in symbols], args.refresh, end)

    print("4/5 Older symbols for renamed stocks whose Yahoo history starts late")
    changes = load_symbol_changes()
    start_cut = pd.Timestamp(config.HISTORY_START) + pd.Timedelta(days=10)
    old_needed = {}
    for s in symbols:
        f = YF_DIR / f"{s}.NS.csv"
        if not f.exists():
            continue
        first = pd.read_csv(f, usecols=["Date"], parse_dates=["Date"])["Date"].min()
        if first > start_cut:
            for old, when in previous_symbols(s, changes):
                old_needed[old] = (s, when, str(first.date()))
    if old_needed:
        print(f"  trying {len(old_needed)} old symbols: {sorted(old_needed)}")
        fetch_yahoo([f"{o}.NS" for o in old_needed], args.refresh, end)
    (RAW / "old_symbols_tried.json").write_text(json.dumps(old_needed, indent=1))

    print("5/5 NSE corporate actions since 2007 (for split/bonus/demerger confirmation)")
    ca_fails = fetch_nse_actions(symbols + list(old_needed), args.refresh)

    manual = [s for s in fails if (config.DATA_DIR / "manual_csv" / f"{s.replace('.NS', '')}.csv").exists()]
    still = sorted(set(fails) - set(manual))
    meta = {"fetched_at": datetime.now().isoformat(timespec="seconds"),
            "yahoo_failures": still, "nse_ca_failures": ca_fails}
    (RAW / "fetch_log.json").write_text(json.dumps(meta, indent=1))
    print(f"Done. Yahoo failures: {still or 'none'}; NSE corporate-action failures: {ca_fails or 'none'}")
    if still:
        print("For each failure, download a CSV (Date, Close, Adj Close) to data/manual_csv/<SYMBOL>.csv:")
        for s in still:
            print(f"  https://finance.yahoo.com/quote/{s}/history")


if __name__ == "__main__":
    main()
