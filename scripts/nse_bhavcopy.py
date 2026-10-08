"""NSE official end-of-day prices (bhavcopy) for a given date — local build only.

Used to (1) find adjustments Yahoo applied silently (not in its action history),
(2) take official opening/closing prices around demergers, (3) spot-check the snapshot.

Formats
* up to 5 Jul 2024: archives.nseindia.com/content/historical/EQUITIES/YYYY/MON/cmDDMONYYYYbhav.csv.zip
* from 8 Jul 2024: archives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_YYYYMMDD_F_0000.csv.zip
Parsed files are cached as data/raw/bhav/YYYYMMDD.csv (SYMBOL, OPEN, CLOSE, PREVCLOSE; EQ series).
"""
from __future__ import annotations

import io
import sys
import time
import zipfile
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config  # noqa: E402

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
CACHE = config.RAW_DIR / "bhav"
UDIFF_START = pd.Timestamp("2024-07-08")
_session: requests.Session | None = None


def _s() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({"User-Agent": UA, "Referer": "https://www.nseindia.com/"})
    return _session


def url_for(d: pd.Timestamp) -> str:
    d = pd.Timestamp(d)
    if d >= UDIFF_START:
        return f"https://archives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{d:%Y%m%d}_F_0000.csv.zip"
    mon = d.strftime("%b").upper()
    return f"https://archives.nseindia.com/content/historical/EQUITIES/{d:%Y}/{mon}/cm{d:%d}{mon}{d:%Y}bhav.csv.zip"


def _parse(content: bytes, d: pd.Timestamp) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        name = z.namelist()[0]
        df = pd.read_csv(z.open(name))
    df.columns = [c.strip() for c in df.columns]
    if "TckrSymb" in df.columns:  # UDiFF
        df = df[df["SctySrs"].astype(str).str.strip() == "EQ"]
        out = pd.DataFrame({"SYMBOL": df["TckrSymb"], "OPEN": df["OpnPric"],
                            "CLOSE": df["ClsPric"], "PREVCLOSE": df["PrvsClsgPric"]})
    else:
        df = df[df["SERIES"].astype(str).str.strip() == "EQ"]
        out = pd.DataFrame({"SYMBOL": df["SYMBOL"], "OPEN": df["OPEN"],
                            "CLOSE": df["CLOSE"], "PREVCLOSE": df["PREVCLOSE"]})
    out["SYMBOL"] = out["SYMBOL"].astype(str).str.strip()
    return out.set_index("SYMBOL")


def bhavcopy(d, tries: int = 4) -> pd.DataFrame | None:
    """Official EQ-series prices for date d, or None if NSE has no file (holiday) / unreachable."""
    d = pd.Timestamp(d).normalize()
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{d:%Y%m%d}.csv"
    miss = CACHE / f"{d:%Y%m%d}.missing"
    if f.exists():
        return pd.read_csv(f, index_col="SYMBOL")
    if miss.exists():
        return None
    for i in range(tries):
        try:
            r = _s().get(url_for(d), timeout=30)
            if r.status_code == 200 and r.content[:2] == b"PK":
                df = _parse(r.content, d)
                df.to_csv(f)
                time.sleep(0.25)
                return df
            if r.status_code == 404:
                miss.write_text("404")
                return None
        except (requests.RequestException, zipfile.BadZipFile):
            pass
        time.sleep(1.5 * 2**i)
    return None


def official_close(symbol: str, d) -> float | None:
    b = bhavcopy(d)
    if b is None or symbol not in b.index:
        return None
    v = b.loc[symbol, "CLOSE"]
    return float(v.iloc[0] if isinstance(v, pd.Series) else v)


INDEX_CACHE = config.RAW_DIR / "index_close"


def index_closes(d, tries: int = 3) -> pd.DataFrame | None:
    """NSE's official closing values of every index on date d (ind_close_all_DDMMYYYY.csv)."""
    d = pd.Timestamp(d).normalize()
    INDEX_CACHE.mkdir(parents=True, exist_ok=True)
    f = INDEX_CACHE / f"{d:%Y%m%d}.csv"
    miss = INDEX_CACHE / f"{d:%Y%m%d}.missing"
    if f.exists():
        return pd.read_csv(f, index_col=0)
    if miss.exists():
        return None
    url = f"https://archives.nseindia.com/content/indices/ind_close_all_{d:%d%m%Y}.csv"
    for i in range(tries):
        try:
            r = _s().get(url, timeout=30)
            if r.status_code == 200 and b"Index Name" in r.content[:200]:
                df = pd.read_csv(io.BytesIO(r.content))
                df.columns = [c.strip() for c in df.columns]
                df["Index Name"] = df["Index Name"].astype(str).str.strip()
                df = df.set_index("Index Name")
                df.to_csv(f)
                time.sleep(0.25)
                return df
            if r.status_code == 404:
                miss.write_text("404")
                return None
        except requests.RequestException:
            pass
        time.sleep(1.5 * 2**i)
    return None


def nifty50_close(d) -> float | None:
    df = index_closes(d)
    if df is None:
        return None
    for name in ("Nifty 50", "NIFTY 50", "S&P CNX Nifty", "CNX Nifty"):
        if name in df.index:
            col = "Closing Index Value" if "Closing Index Value" in df.columns else df.columns[4]
            return float(df.loc[name, col])
    return None
