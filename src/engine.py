"""Orchestrates every result the app shows, for any pair of portfolios.

Used twice with the same code: at build time by scripts/precompute.py (default portfolios, every
catalogue event) and in the browser for custom picks. Everything returned is percentages or
₹1-normalised paths — rupee figures are percentage × the client's amount, applied in the UI, so
amount changes never trigger recomputation.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import classify as CL
from . import config
from . import data as D
from . import events as EV
from . import metrics as M
from . import optimize as O
from . import regimes as RG
from . import stats_tests as ST
from . import universe as U
from . import var_es as V

CS = (0.95, 0.99, config.ES_BASEL)


# ---------------------------------------------------------------- helpers
def _f(x):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else float(x)


def _w(series: pd.Series) -> dict:
    return {k: round(float(v), 6) for k, v in series.items()}


def window_returns(symbols, start, end):
    R = D.window(D.returns(), start, end)[list(symbols)]
    m = D.window(D.market_returns(), start, end)
    return R, m


def industries_of(symbols) -> list[str]:
    u = D.universe()
    return [u.loc[s, "industry"] for s in symbols]


def industry_weights(w: pd.Series) -> dict:
    u = D.universe()
    s = w.groupby(u.loc[w.index, "industry"]).sum().sort_values(ascending=False)
    return {k: round(float(v), 6) for k, v in s.items()}


def mu_sigma(R: pd.DataFrame, shrink: bool = False):
    mu = (R.mean() * config.TRADING_DAYS).to_numpy()
    S = M.cov_matrix(R, shrink).to_numpy()
    return mu, S


# ---------------------------------------------------------------- portfolio set-up (current window)
def build_portfolio(name: str, symbols: list[str], objective: str, shrink: bool = False,
                    cloud_k: int = config.RANDOM_PORTFOLIOS) -> dict:
    cal = D.calendar()
    cs, ce = RG.current_window(cal)
    R, m = window_returns(symbols, cs, ce)
    cons = O.build_constraints(industries_of(symbols))
    mu, S = mu_sigma(R, shrink)
    fell_back = False
    if objective == "max_sharpe":
        w, fell_back = O.max_sharpe(mu, S, cons)
    else:
        w = O.min_variance(mu, S, cons)
    viol = O.check(w, cons)
    wser = pd.Series(w, index=symbols)
    eq = pd.Series(1 / len(symbols), index=symbols)
    fr = O.frontier(mu, S, cons)
    cl = O.cloud(mu, S, cons, k=cloud_k)
    st = O.port_stats(w, mu, S)
    return {
        "name": name, "symbols": list(symbols), "objective": objective, "fell_back_to_minvar": bool(fell_back),
        "constraints": {"w_min": cons.w_min, "w_max": cons.w_max, "ind_max": cons.ind_max, "warnings": cons.warnings,
                        "violations": viol},
        "weights": _w(wser), "equal_weights": _w(eq), "industry_weights": industry_weights(wser),
        "mu": {s: float(x) for s, x in zip(symbols, mu)}, "vol_i": {s: float(np.sqrt(S[i, i])) for i, s in enumerate(symbols)},
        "expected_return": st["ret"], "expected_vol": st["vol"], "sharpe": st["sharpe"],
        "target_return": st["ret"],
        "frontier": {"rets": fr["rets"].tolist(), "vols": fr["vols"].tolist(), "r_min": fr["r_min"], "r_max": fr["r_max"],
                     "minvar": O.port_stats(fr["w_minvar"], mu, S), "minvar_weights": _w(pd.Series(fr["w_minvar"], index=symbols))},
        "cloud": {"ret": cl["ret"].round(5).tolist(), "vol": cl["vol"].round(5).tolist()},
        "var_before_after": {"equal": var_block(R, eq), "optimised": var_block(R, wser)},
        "window": {"start": str(cs.date()), "end": str(ce.date())},
    }


def var_block(R: pd.DataFrame, w: pd.Series) -> dict:
    """{method: {conf: {var, es}}} as plain floats (1-day)."""
    res = V.all_methods(R, w, CS)
    out = {m: {str(c): {"var": res[m][c]["var"], "es": res[m][c]["es"]} for c in CS} for m in V.METHODS}
    out["t_dof"] = res["_t_dof"]
    return out


# ---------------------------------------------------------------- evidence for "the call" (§6.3)
def evidence(pa: dict, pb: dict, resamples: int = config.BOOTSTRAP_RESAMPLES) -> dict:
    cal = D.calendar()
    start = cal[-config.CLASSIFICATION_YEARS * config.TRADING_DAYS]
    table = U.classification()
    u = D.universe()
    out = {"window": {"start": str(start.date()), "end": str(cal[-1].date())}}
    port_r = {}
    for p in (pa, pb):
        w = pd.Series(p["weights"])
        R, m = window_returns(p["symbols"], start, cal[-1])
        r = M.portfolio_returns(R, w)
        port_r[p["name"]] = r
        Sigma = (R.fillna(0).cov() * config.TRADING_DAYS).to_numpy()
        betas = table.loc[p["symbols"], "beta"]
        caps = w.groupby(u.loc[w.index, "cap_bucket"]).sum()
        out[p["name"]] = {
            "weighted_beta": float((w * betas).sum()), "portfolio_beta": M.beta(r, m),
            "portfolio_vol": float(np.sqrt(w.to_numpy() @ Sigma @ w.to_numpy())),
            "realised_vol": float(M.ann_vol(r)), "max_drawdown": M.max_drawdown(r),
            "avg_pairwise_corr": M.avg_pairwise_corr(R), "cap_mix": {k: float(v) for k, v in caps.items()},
            "industry_weights": industry_weights(w), "ann_return": float(M.ann_return(r)), "sharpe": M.sharpe(r),
            "stock_betas": {s: float(table.loc[s, "beta"]) for s in p["symbols"]},
            "stock_vols": {s: float(table.loc[s, "volatility"]) for s in p["symbols"]},
            "stock_labels": {s: table.loc[s, "label"] for s in p["symbols"]},
            "corr": R.corr().round(3).to_numpy().tolist(),
        }
    ci = ST.vol_ratio_ci(port_r[pa["name"]], port_r[pb["name"]], resamples=resamples)
    out["vol_ratio"] = {k: v for k, v in ci.items() if k != "draws"}
    out["vol_ratio"]["draws"] = np.round(ci["draws"], 4).tolist()
    out["vol_median"] = float(table["vol_median"].iloc[0])
    return out


# ---------------------------------------------------------------- one portfolio in one regime (§6.8, §6.9)
def regime_result(p: dict, start, end, universe_labels: pd.DataFrame | None = None,
                  frontier_points: int = config.FRONTIER_POINTS) -> dict:
    symbols = p["symbols"]
    w = pd.Series(p["weights"])
    R, m = window_returns(symbols, start, end)
    if R.isna().all().any():
        missing = [s for s in symbols if R[s].isna().all()]
        return {"available": False, "reason": f"no data for {', '.join(missing)} in this window"}
    r = M.portfolio_returns(R, w)
    risk = var_block(R, w)
    # benchmark in the same window
    nifty_r = m
    nh_var, nh_es = V.historical(nifty_r.to_numpy(), 0.99)
    # label stability
    stab = None
    if universe_labels is not None and len(universe_labels):
        lab = universe_labels
        want = CL.HIGH if p["name"] == "A" else CL.LOW
        present = [s for s in symbols if s in lab.index]
        stab = {"same": int(sum(lab.loc[s, "label"] == want for s in present)), "of": len(present),
                "labels": {s: lab.loc[s, "label"] for s in present}, "vol_median": float(lab["vol_median"].iloc[0])}
    # buy-and-hold replay (₹1 at the window start)
    P = D.window(D.prices(), start, end)[symbols].ffill()
    bh = M.buy_and_hold_value(P, w, 1.0)
    # test #2: target-return optimisation in this regime
    cons = O.build_constraints(industries_of(symbols))
    mu, S = mu_sigma(R.fillna(0.0))
    tc = O.solve_target_case(mu, S, cons, p["target_return"])
    w_reg = pd.Series(tc["weights"], index=symbols)
    fr = O.frontier(mu, S, cons, points=frontier_points)
    today_stats = O.port_stats(w.to_numpy(), mu, S)
    eff_vol = O.efficient_vol_at(fr, today_stats["ret"])
    return {
        "available": True, "start": str(pd.Timestamp(start).date()), "end": str(pd.Timestamp(end).date()), "days": int(len(r)),
        "risk": risk,
        "volatility": float(M.ann_vol(r)), "beta": M.beta(r, m), "max_drawdown": M.max_drawdown(r),
        "worst_day": float(r.min()), "worst_day_date": str(r.idxmin().date()), "avg_pairwise_corr": M.avg_pairwise_corr(R),
        "ann_return": float(M.ann_return(r)), "total_return": float((1 + r).prod() - 1),
        "nifty": {"es99": nh_es, "var99": nh_var, "max_drawdown": M.max_drawdown(nifty_r), "volatility": float(M.ann_vol(nifty_r)),
                  "total_return": float((1 + nifty_r).prod() - 1)},
        "stability": stab,
        "returns": {"dates": [str(d.date()) for d in r.index], "port": np.round(r.to_numpy(), 6).tolist()},
        "replay": {"value": np.round(bh.to_numpy(), 5).tolist(), "low": float(min(bh.min(), 1.0)),
                   "low_date": str(bh.idxmin().date()), "largest_fall": float(max(0.0, 1 - bh.min())), "end": float(bh.iloc[-1])},
        "test2": {
            "case": tc["case"], "target": p["target_return"], "r_minvar": tc["r_minvar"], "r_max": tc["r_max"],
            "weights": _w(w_reg), "industry_weights": industry_weights(w_reg),
            "ret": tc["ret"], "vol": tc["vol"], "turnover": O.turnover(w.to_numpy(), w_reg.to_numpy()),
            "today_in_regime": today_stats, "efficient_vol_same_return": eff_vol,
            "efficiency_gap": max(0.0, today_stats["vol"] - eff_vol),
            "frontier": {"rets": fr["rets"].tolist(), "vols": fr["vols"].tolist()},
            "var_after": var_block(R, w_reg),
        },
    }


def nifty_replay(start, end) -> dict:
    c = D.window(D.benchmark()["NIFTY50"], start, end)
    v = c / c.iloc[0]
    return {"value": np.round(v.to_numpy(), 5).tolist(), "low": float(min(v.min(), 1.0)), "largest_fall": float(max(0.0, 1 - v.min())),
            "dates": [str(d.date()) for d in v.index]}


def labels_in_window(start, end) -> pd.DataFrame:
    """Re-run the §6.2 rule with the regime's own data (all stocks with data for the window)."""
    t = U.metrics_table(start, end)
    return CL.classify(t) if len(t) else t


# ---------------------------------------------------------------- bootstrap noise (§6.9)
def bootstrap_noise(p: dict, resamples: int, progress=None) -> dict:
    cal = D.calendar()
    cs, ce = RG.current_window(cal)
    R, _ = window_returns(p["symbols"], cs, ce)
    cons = O.build_constraints(industries_of(p["symbols"]))
    target = p["target_return"]

    def solve(Rb):
        mu, S = mu_sigma(Rb)
        return O.solve_target_case(mu, S, cons, target, starts=1)["weights"]

    mu0, S0 = mu_sigma(R.fillna(0.0))
    base = O.solve_target_case(mu0, S0, cons, target)["weights"]
    W = ST.bootstrap_target_weights(R, solve, resamples, progress=progress)
    turn = np.array([O.turnover(base, x) for x in W])
    lo, hi = np.quantile(W, [0.05, 0.95], axis=0)
    return {"resamples": int(len(W)), "base": _w(pd.Series(base, index=p["symbols"])),
            "band_lo": _w(pd.Series(lo, index=p["symbols"])), "band_hi": _w(pd.Series(hi, index=p["symbols"])),
            "turnover_noise": np.round(turn, 5).tolist(), "turnover_p95": float(np.quantile(turn, 0.95)),
            "turnover_median": float(np.median(turn))}


# ---------------------------------------------------------------- events
def resolve_events() -> dict:
    close = D.benchmark()["NIFTY50"]
    return EV.resolve_all(close, D.market_returns())


def event_payload(ev: dict) -> dict:
    """JSON-safe event description."""
    def ts(x):
        return None if x is None else str(pd.Timestamp(x).date())
    anc = {k: (ts(v) if isinstance(v, pd.Timestamp) else v) for k, v in (ev.get("anchor") or {}).items()}
    return {
        "id": ev["id"], "name": ev["name"], "type": ev["type"], "story": ev.get("story", ""), "source": ev.get("source", ""),
        "label": ev.get("label", ev["name"]), "available": bool(ev.get("available")),
        "notes": ev.get("notes", []), "support": ev.get("support", ""), "overlaps": ev.get("overlaps", []),
        "search": [ts(ev.get("search_start")), ts(ev.get("search_end"))], "anchor": anc,
        "windows": {k: (None if v is None else [ts(v[0]), ts(v[1])]) for k, v in ev["windows"].items()},
    }


def run_all(pa_syms: list[str], pb_syms: list[str], event_ids=None, modes=("standard", "event_only"),
            resamples: int = config.BOOTSTRAP_RESAMPLES, cloud_k: int = config.RANDOM_PORTFOLIOS,
            progress=None, with_bootstrap: bool = True) -> dict:
    """Full result set: portfolios, evidence, current regime, every requested event × window mode."""
    pa = build_portfolio("A", pa_syms, config.OBJECTIVE_A, cloud_k=cloud_k)
    pb = build_portfolio("B", pb_syms, config.OBJECTIVE_B, cloud_k=cloud_k)
    evs = resolve_events()
    ids = [k for k, v in evs.items() if v["available"]] if event_ids is None else list(event_ids)
    cal = D.calendar()
    cs, ce = RG.current_window(cal)
    out = {"as_of": D.as_of(), "portfolios": {"A": pa, "B": pb}, "events": {k: event_payload(v) for k, v in evs.items()},
           "current": {}, "regimes": {}, "nifty": {}}
    lab_cur = labels_in_window(cs, ce)
    out["current"] = {"A": regime_result(pa, cs, ce, lab_cur), "B": regime_result(pb, cs, ce, lab_cur),
                      "nifty": nifty_replay(cs, ce), "start": str(cs.date()), "end": str(ce.date())}
    jobs = [(i, md) for i in ids for md in modes if evs[i]["windows"].get(md) is not None]
    for n, (i, md) in enumerate(jobs, 1):
        s, e = evs[i]["windows"][md]
        lab = labels_in_window(s, e)
        key = f"{i}|{md}"
        out["regimes"][key] = {"A": regime_result(pa, s, e, lab), "B": regime_result(pb, s, e, lab),
                               "nifty": nifty_replay(s, e), "start": str(pd.Timestamp(s).date()), "end": str(pd.Timestamp(e).date())}
        if progress:
            progress(n / max(len(jobs), 1), evs[i]["name"])
    out["evidence"] = evidence(pa, pb, resamples=resamples)
    if with_bootstrap:
        out["bootstrap"] = {"A": bootstrap_noise(pa, resamples), "B": bootstrap_noise(pb, resamples)}
    out["regime_finder"] = regime_finder()
    return out


def regime_finder() -> dict:
    close = D.benchmark()["NIFTY50"]
    mret = D.market_returns()
    cal = mret.index
    cur = RG.current_window(cal)
    ac = RG.auto_crisis(close.loc[cal[0]:])
    crisis_c = RG.candidates(close.loc[cal[0]:], mret, "crisis", exclude=[cur])
    calm_c = RG.candidates(close.loc[cal[0]:], mret, "calm", exclude=[cur, (ac["start"], ac["end"])])
    return {"crisis_candidates": crisis_c, "calm_candidates": calm_c,
            "current": RG.window_stats(close, mret, cur[0], cur[1])}


# ---------------------------------------------------------------- scoreboard (§6.5)
def scoreboard(results: dict, mode: str = "standard") -> list[dict]:
    rows = []
    for key, reg in results["regimes"].items():
        eid, md = key.split("|")
        if md != mode or eid.startswith("auto_"):
            continue  # the auto picks duplicate catalogue events; the scoreboard is the catalogue
        ev = results["events"][eid]
        a, b = reg["A"], reg["B"]
        if not (a.get("available") and b.get("available")):
            continue
        es_a = a["risk"]["Historical"]["0.99"]["es"]
        es_b = b["risk"]["Historical"]["0.99"]["es"]
        rows.append({
            "id": eid, "event": ev["name"], "type": ev["type"], "start": reg["start"], "end": reg["end"],
            "es99_A": es_a, "es99_B": es_b, "vol_A": a["volatility"], "vol_B": b["volatility"],
            "mdd_A": a["max_drawdown"], "mdd_B": b["max_drawdown"],
            "fall_A": a["replay"]["largest_fall"], "fall_B": b["replay"]["largest_fall"],
            "nifty_fall": reg["nifty"]["largest_fall"],
            "label_held": bool(es_a > es_b and a["volatility"] > b["volatility"]),
            "b_held_up": bool(es_b < b["nifty"]["es99"] and b["max_drawdown"] < b["nifty"]["max_drawdown"]),
        })
    return rows
