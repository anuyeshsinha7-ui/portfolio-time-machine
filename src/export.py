"""Every results table as one Excel workbook (openpyxl; runs in the browser too)."""
from __future__ import annotations

import io

import pandas as pd

from . import config
from . import data as D


def workbook(ctx_parts: dict) -> bytes:
    """ctx_parts: {'portfolios', 'evidence', 'regimes' [(name, reg, ev)], 'scoreboard', 'universe', 'events', 'amounts'}."""
    P, ev = ctx_parts["portfolios"], ctx_parts["evidence"]
    aa, ab = ctx_parts["amounts"]
    sheets = {}
    sheets["Read me"] = pd.DataFrame({"Item": ["Project", "Data as of", "Amount A (₹)", "Amount B (₹)", "Risk-free rate", "Note"],
                                      "Value": [config.APP_NAME, D.as_of(), aa, ab, config.RISK_FREE_RATE,
                                                "Educational project — not investment advice."]})
    rows = []
    for k in ("A", "B"):
        p = P[k]
        amt = aa if k == "A" else ab
        for s, w in p["weights"].items():
            rows.append({"Portfolio": k, "Symbol": s, "Weight": w, "₹ target": w * amt, "μ (annual)": p["mu"][s],
                         "σ (annual)": p["vol_i"][s]})
    sheets["Weights today"] = pd.DataFrame(rows)
    sheets["Risk call"] = pd.DataFrame([{"Portfolio": k, **{m: ev[k][m] for m in ("weighted_beta", "portfolio_beta", "portfolio_vol",
                                                                               "max_drawdown", "avg_pairwise_corr", "ann_return", "sharpe")}}
                                        for k in ("A", "B")])
    vr = ev["vol_ratio"]
    sheets["Risk call"].loc[len(sheets["Risk call"])] = {"Portfolio": "σA/σB", "weighted_beta": vr["ratio"], "portfolio_beta": vr["lo"],
                                                         "portfolio_vol": vr["hi"]}
    rows, t2 = [], []
    for name, reg, e in ctx_parts["regimes"]:
        for k in ("A", "B"):
            r = reg[k]
            base = {"Period": name, "Event": e["name"] if e else "Current", "Start": reg["start"], "End": reg["end"], "Portfolio": k}
            for m, blk in r["risk"].items():
                if m == "t_dof":
                    continue
                for c, v in blk.items():
                    rows.append({**base, "Method": m, "Confidence": c, "VaR": v["var"], "ES": v["es"]})
            t = r["test2"]
            t2.append({**base, "Case": t["case"], "Target": t["target"], "Optimal return": t["ret"], "Optimal vol": t["vol"],
                       "Turnover": t["turnover"], "Efficiency gap": t["efficiency_gap"],
                       **{f"w {s}": w for s, w in t["weights"].items()}})
    sheets["VaR & ES"] = pd.DataFrame(rows)
    sheets["Test 2"] = pd.DataFrame(t2)
    if ctx_parts.get("scoreboard"):
        sheets["Scoreboard"] = pd.DataFrame(ctx_parts["scoreboard"])
    sheets["Universe"] = ctx_parts["universe"].reset_index()
    sheets["Events"] = pd.DataFrame([{"id": e["id"], "name": e["name"], "type": e["type"], "available": e["available"],
                                      "window": " → ".join(e["windows"]["standard"] or []), "support": e.get("support", ""),
                                      "source": e.get("source", "")} for e in ctx_parts["events"].values()])
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        for name, df in sheets.items():
            df.to_excel(xw, sheet_name=name[:31], index=False)
    return buf.getvalue()
