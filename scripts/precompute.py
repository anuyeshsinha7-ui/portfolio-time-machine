"""Build-time results for the default portfolios × every catalogue event (both window modes),
the universe classification table and the regime-finder evidence → results/*.json.

The browser loads these and only recomputes when the client changes stocks or picks a custom range.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src import config  # noqa: E402
from src import data as D  # noqa: E402
from src import engine as E  # noqa: E402
from src import universe as U  # noqa: E402


class Enc(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, (np.floating,)):
            return None if np.isnan(o) else round(float(o), 7)
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.bool_,)):
            return bool(o)
        if isinstance(o, (pd.Timestamp,)):
            return str(o.date())
        if isinstance(o, np.ndarray):
            return o.tolist()
        return super().default(o)


def clean(o):
    """Round floats and turn NaN into None so the JSON is compact and valid."""
    if isinstance(o, float):
        return None if np.isnan(o) else round(o, 7)
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    return o


def official(evs: dict, kind: str) -> str:
    want = config.OFFICIAL_CRISIS_EVENT if kind == "crisis" else config.OFFICIAL_CALM_EVENT
    if want != "auto" and want in evs and evs[want]["available"]:
        return want
    return "auto_crisis" if kind == "crisis" else "auto_calm"


def main() -> None:
    t0 = time.time()
    out_dir = config.RESULTS_DIR
    out_dir.mkdir(exist_ok=True)

    table = U.classification()
    picks = U.default_portfolios(table)
    cols = ["company", "industry", "cap_bucket", "status", "first_date", "beta", "volatility", "ann_return", "max_drawdown",
            "sharpe", "sortino", "skew", "excess_kurtosis", "downside_dev", "cagr", "worst_day", "label", "risk_score",
            "beta_pct", "vol_pct", "beta_full", "vol_full", "label_full", "vol_median", "window_start"]
    uni = table[cols].reset_index().rename(columns={"index": "symbol"})
    (out_dir / "universe.json").write_text(json.dumps(clean(uni.to_dict(orient="records")), cls=Enc, separators=(",", ":")))
    print(f"universe: {len(uni)} stocks classified ({uni['label'].value_counts().to_dict()})")
    print(f"default A: {picks['A']}\ndefault B: {picks['B']}")

    def prog(f, name):
        print(f"  {f:5.0%}  {name}", flush=True)

    res = E.run_all(picks["A"], picks["B"], progress=prog)
    res["picks"] = picks
    res["official"] = {"crisis": official(res["events"], "crisis"), "calm": official(res["events"], "calm")}
    res["scoreboard"] = {"standard": E.scoreboard(res, "standard"), "event_only": E.scoreboard(res, "event_only")}
    res["config"] = {k: getattr(config, k) for k in (
        "RISK_FREE_RATE", "RISK_FREE_SOURCE", "W_MIN", "W_MAX", "INDUSTRY_MAX", "REGIME_DAYS", "EVENT_PRE_DAYS",
        "MIN_WINDOW_DAYS", "BOOTSTRAP_RESAMPLES", "BLOCK_DAYS", "MC_DRAWS", "SEED", "CLASSIFICATION_YEARS")}
    (out_dir / "default.json").write_text(json.dumps(clean(res), cls=Enc, separators=(",", ":")))
    size = (out_dir / "default.json").stat().st_size
    print(f"results/default.json {size / 1e6:.2f} MB in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
