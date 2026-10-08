"""Event catalogue and data-anchored event windows (brief §6.5).

Dates in data/events.json are only *search ranges*. The window itself comes from the Nifty 50:
* crisis → the deepest peak-to-trough fall inside the range;
* calm   → the lowest-volatility stretch inside the range.
Two window modes:
* standard   → REGIME_DAYS (252) days: crises start EVENT_PRE_DAYS before the peak; a calm window is the
               lowest-volatility 252-day window whose midpoint lies in the range. Equal length everywhere,
               so comparisons are fair.
* event_only → crisis: peak to trough; calm: the calm stretch; padded symmetrically to MIN_WINDOW_DAYS.
No window may overlap the Current window: a window that would is slid earlier (same length) and the
label says so; if the event no longer fits, it is marked unavailable.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import config
from . import regimes as RG

AUTO_CRISIS, AUTO_CALM, CUSTOM = "auto_crisis", "auto_calm", "custom"


def load_catalogue(path=config.EVENTS_FILE) -> list[dict]:
    return json.loads(path.read_text())["events"]


def _pos(cal, d):
    return int(cal.searchsorted(pd.Timestamp(d)))


def anchor_crisis(close: pd.Series, start, end) -> dict:
    c = close.loc[pd.Timestamp(start):pd.Timestamp(end)]
    peak, trough, fall = RG.max_dd_window(c)
    return {"peak": peak, "trough": trough, "fall": fall}


def anchor_calm(mret: pd.Series, start, end, days: int = config.CALM_ANCHOR_DAYS,
                n: int = config.REGIME_DAYS) -> dict:
    """Lowest-volatility `days` stretch inside the range (event-only window) and the lowest-volatility
    n-day window whose midpoint lies inside the range (standard window)."""
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    r = mret.loc[s:e]
    days = min(days, len(r))
    rv = r.rolling(days).std(ddof=1).dropna()
    ce = rv.idxmin()
    epos = r.index.get_loc(ce)
    cs = r.index[epos - days + 1]
    cal = mret.index
    roll = mret.rolling(n).std(ddof=1)
    best, best_v = None, np.inf
    for end_pos in range(n - 1, len(cal)):
        mid = cal[end_pos - n // 2]
        if mid < s or mid > e:
            continue
        v = roll.iloc[end_pos]
        if v < best_v:
            best, best_v = (cal[end_pos - n + 1], cal[end_pos]), v
    return {"calm_start": cs, "calm_end": ce, "calm_vol": float(rv.min() * np.sqrt(config.TRADING_DAYS)),
            "std_start": best[0] if best else None, "std_end": best[1] if best else None,
            "std_vol": float(best_v * np.sqrt(config.TRADING_DAYS)) if best else None}


def _pad(cal, s: int, e: int, min_days: int) -> tuple[int, int]:
    n = e - s + 1
    if n < min_days:
        extra = min_days - n
        s -= extra // 2
        e += extra - extra // 2
    if s < 0:
        e, s = e - s, 0
    if e > len(cal) - 1:
        s, e = s - (e - (len(cal) - 1)), len(cal) - 1
    return max(s, 0), e


def build_windows(anchor: dict, kind: str, cal: pd.DatetimeIndex, current: tuple) -> dict:
    """Standard and event-only windows for an anchored event, honouring the Current-window rule."""
    n, pre, mn = config.REGIME_DAYS, config.EVENT_PRE_DAYS, config.MIN_WINDOW_DAYS
    cur_start = _pos(cal, current[0])
    if kind == "crisis":
        p, t = _pos(cal, anchor["peak"]), _pos(cal, anchor["trough"])
        std = (p - pre, p - pre + n - 1)
        ev = _pad(cal, p, t, mn)
        must_contain = (p, p)  # the peak must stay inside
    else:
        a, b = _pos(cal, anchor["calm_start"]), _pos(cal, anchor["calm_end"])
        if anchor.get("std_start") is not None:
            sa = _pos(cal, anchor["std_start"])
            std = (sa, sa + n - 1)
        else:
            mid = (a + b) // 2
            std = (mid - n // 2, mid - n // 2 + n - 1)
        ev = _pad(cal, a, b, mn)
        must_contain = (a, b)
    out, notes = {}, []
    for mode, (s, e) in (("standard", std), ("event_only", ev)):
        length = e - s + 1
        if s < 0:
            s, e = 0, length - 1
            notes.append(f"{mode}: started at the first available day")
        if e >= cur_start:
            shift = e - (cur_start - 1)
            s, e = s - shift, e - shift
            if s < 0 or s > must_contain[0]:
                out[mode] = None
                notes.append(f"{mode}: would overlap the Current window and cannot be moved without losing the event")
                continue
            notes.append(f"{mode}: moved {shift} trading days earlier so it does not overlap the Current window")
        out[mode] = (cal[s], cal[e])
    out["notes"] = notes
    return out


def resolve_all(close: pd.Series, mret: pd.Series, catalogue: list[dict] | None = None) -> dict:
    """Every catalogue event plus the automatic picks, anchored on the data.

    Returns {id: event dict} where each event has name, type, story, source, anchor, windows,
    label, available, notes and support (the data evidence used to keep or drop it)."""
    cal = close.index
    catalogue = catalogue if catalogue is not None else load_catalogue()
    cur = RG.current_window(cal)
    out: dict = {}

    ac = RG.auto_crisis(close)
    acal = RG.auto_calm(mret, exclude=[cur, (ac["start"], ac["end"])])
    out[AUTO_CRISIS] = {
        "id": AUTO_CRISIS, "name": "Auto: deepest drawdown", "type": "crisis",
        "story": ("The window around the Nifty 50's deepest peak-to-trough fall in the whole sample, found by "
                  "the data with no human choice. It starts 21 trading days before the pre-crash peak."),
        "source": "Computed from the Nifty 50 snapshot",
        "anchor": {"peak": ac["peak"], "trough": ac["trough"], "fall": ac["fall"]},
        "windows": {"standard": (ac["start"], ac["end"]),
                    "event_only": tuple(cal[list(_pad(cal, _pos(cal, ac["peak"]), _pos(cal, ac["trough"]), config.MIN_WINDOW_DAYS))])},
        "notes": [], "available": True,
    }
    out[AUTO_CALM] = {
        "id": AUTO_CALM, "name": "Auto: calmest year", "type": "calm",
        "story": ("The 252-day stretch with the lowest Nifty 50 volatility in the sample that overlaps neither "
                  "the Current window nor the automatic crisis window."),
        "source": "Computed from the Nifty 50 snapshot",
        "anchor": {"calm_start": acal["start"], "calm_end": acal["end"], "calm_vol": acal["vol"]},
        "windows": {"standard": (acal["start"], acal["end"]), "event_only": (acal["start"], acal["end"])},
        "notes": [], "available": True,
    }

    for ev in catalogue:
        s, e = pd.Timestamp(ev["search_start"]), pd.Timestamp(ev["search_end"])
        item = {k: ev[k] for k in ("id", "name", "type", "story", "source")}
        item.update({"search_start": s, "search_end": e, "notes": []})
        if s < cal[0] or s > cal[-1]:
            item.update(available=False, windows={"standard": None, "event_only": None},
                        support="outside the data", anchor={})
            out[ev["id"]] = item
            continue
        if ev["type"] == "crisis":
            anc = anchor_crisis(close, s, e)
            support_ok = anc["fall"] >= ev.get("min_fall", 0.07)
            item["support"] = f"Nifty 50 fell {anc['fall']:.1%} peak to trough inside the search range"
        else:
            anc = anchor_calm(mret, s, e)
            full_med = float(RG.rolling_vol(mret, config.CALM_ANCHOR_DAYS).median())
            support_ok = anc["calm_vol"] < full_med
            item["support"] = (f"lowest {config.CALM_ANCHOR_DAYS}-day Nifty 50 volatility in the range "
                               f"{anc['calm_vol']:.1%} vs full-sample median {full_med:.1%}")
        w = build_windows(anc, ev["type"], cal, cur)
        item.update(anchor=anc, windows={"standard": w["standard"], "event_only": w["event_only"]},
                    notes=w["notes"], available=bool(support_ok and w["standard"] is not None))
        if not support_ok:
            item["notes"].append("dropped: the Nifty 50 data does not support this as a "
                                 + ("crisis (fall under the threshold)" if ev["type"] == "crisis" else "calm period"))
        out[ev["id"]] = item

    # overlap flags (standard windows)
    ids = [k for k, v in out.items() if v["available"]]
    for a in ids:
        wa = out[a]["windows"]["standard"]
        out[a]["overlaps"] = [out[b]["name"] for b in ids if b != a and out[b]["windows"]["standard"]
                              and RG.overlaps(wa, out[b]["windows"]["standard"])]
    for k, v in out.items():
        v["label"] = label(v, close)
    return out


def window_of(ev: dict, mode: str = config.EVENT_WINDOW_MODE):
    w = ev["windows"].get(mode)
    return w if w is not None else ev["windows"].get("standard")


def nifty_change(close: pd.Series, ev: dict) -> float:
    """Headline move used in the label: the anchored fall for a crisis, the window return for calm."""
    if ev["type"] == "crisis" and ev.get("anchor", {}).get("fall") is not None:
        return -ev["anchor"]["fall"]
    w = window_of(ev, "standard")
    c = close.loc[w[0]:w[1]]
    return float(c.iloc[-1] / c.iloc[0] - 1)


def label(ev: dict, close: pd.Series, mode: str = "standard") -> str:
    """'COVID-19 crash · Dec 2019 – Dec 2020 · Nifty −38%' (+ overlap flags)."""
    w = ev["windows"].get(mode) or ev["windows"].get("standard")
    if not ev.get("available") or w is None:
        return f"{ev['name']} · not available"
    chg = nifty_change(close, ev)
    sign = "−" if chg < 0 else "+"
    txt = f"{ev['name']} · {w[0]:%b %Y} – {w[1]:%b %Y} · Nifty {sign}{abs(chg):.0%}"
    if ev.get("overlaps"):
        txt += " · overlaps " + ", ".join(ev["overlaps"][:2])
    return txt


def coverage(first_dates: pd.Series, ev: dict, mode: str = "standard") -> dict:
    """{symbol: reason or None} — None when the stock has data for the whole window."""
    w = window_of(ev, mode)
    out = {}
    for s, d in first_dates.items():
        if w is None:
            out[s] = "event not available"
        elif pd.isna(d) or pd.Timestamp(d) > pd.Timestamp(w[0]):
            yr = "—" if pd.isna(d) else pd.Timestamp(d).year
            out[s] = f"{s} listed in {yr} — not available for this event"
        else:
            out[s] = None
    return out


def custom_event(start, end, close: pd.Series, kind: str) -> dict:
    """A user-chosen date range (at least MIN_WINDOW_DAYS trading days)."""
    cal = close.index
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    days = int(((cal >= s) & (cal <= e)).sum())
    if days < config.MIN_WINDOW_DAYS:
        raise ValueError(f"A custom range needs at least {config.MIN_WINDOW_DAYS} trading days; this one has {days}.")
    c = close.loc[s:e]
    peak, trough, fall = RG.max_dd_window(c)
    w = (c.index[0], c.index[-1])
    ev = {"id": CUSTOM, "name": "Custom range", "type": kind, "story": "A date range you chose.",
          "source": "Your selection", "anchor": {"peak": peak, "trough": trough, "fall": fall},
          "windows": {"standard": w, "event_only": w}, "notes": [], "available": True, "overlaps": []}
    ev["label"] = label(ev, close)
    return ev
