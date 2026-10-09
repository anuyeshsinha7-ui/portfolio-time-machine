"""Step 6 — Rebalance: in each ticked period, how would the optimum weights change? (brief §6.9)."""
import numpy as np
import pandas as pd
import streamlit as st

from src import charts as CH
from src import narrative as NR
from src import ui

s = st.session_state
left, right = ui.split()
ctx = ui.context()
k = ctx.ck()
boot = ctx.bootstrap()
CASE = {"reachable": "Reachable — the portfolio that hits today's target return with the least risk",
        "below_minvar": "Target below that period's minimum-variance return — the optimiser picks minimum variance (beats the target with less risk)",
        "unreachable": "Unreachable in that period — the closest it gets is the highest return the constraints allow"}
PLAIN = {"reachable": "could still hit today's target return", "below_minvar": "beats today's target with less risk",
         "unreachable": "can't reach today's target return"}
u = ui.universe_table()
evs_all = ui.default_results()["events"]
results = [(eid,) + ui.regime_for(ctx, eid) for eid in s["bt_events"]]
results = [(eid, reg, ev) for eid, reg, ev, prob in results if reg is not None]

with left:
    ui.hero("Rebalance", "How should the weights change?",
            "In each period, the optimiser looks for the least risky mix that still earns today's expected return", "")
    ui.portfolio_badge()
    if not results:
        ui.note("Tick some periods on the Backtest screen first.", "☝️", "warn")
    which = st.segmented_control("Portfolio", ["A", "B"], format_func=lambda x: "A · Bold" if x == "A" else "B · Steady",
                                 default="A", key="t2_which", required=True)
    p = ctx.P[which]
    amt = ctx.amount(which)
    ui.tiles([("Today's target return", ui.pct(p["target_return"]), "a year, with today's weights", which.lower()),
              ("Your amount", ui.inr_short(amt), f"Portfolio {which}", which.lower())])
    if not boot and results:
        if st.button("Run the noise check (is a change real?)", width="stretch"):
            ui.compute_bootstrap(ctx)
            st.rerun()
    ui.section("Money you'd need to move")
    rows = []
    for eid, reg, ev in results:
        t2 = reg[which]["test2"]
        if boot:
            real = t2["turnover"] > boot[which]["turnover_p95"]
            c = ui.chip("real change", "bad") if real else ui.chip("just noise", "ok")
        else:
            c = ui.chip("run check", "grey")
        rows.append(("🌪️" if ev["type"] == "crisis" else "🌤️", ui.esc(ui.short(ev)),
                     f"Optimiser {PLAIN[t2['case']]} · move {ui.pct(t2['turnover'], 0)} of the money", ui.inr_short(t2["turnover"] * amt), c))
    ui.list_rows(rows)
    if boot:
        ui.note(f"Random noise in 12 months of prices alone can shuffle up to <b>{ui.pct(boot[which]['turnover_p95'], 0)}</b> "
                f"({ui.inr_short(boot[which]['turnover_p95'] * amt)}). Only bigger moves count as a real change.", "🎲")
    if results:
        ui.section("The new weights", "today → optimum in that period")
        names = {eid: ui.short(ev) for eid, reg, ev in results}
        if "t2_focus" not in s or s["t2_focus"] not in names:
            s["t2_focus"] = results[0][0]
        focus = st.selectbox("Period", list(names), format_func=names.get, key="t2_focus")
        reg = next(r for e_, r, _ in results if e_ == focus)
        cw, tw = pd.Series(reg[which]["test2"]["weights"]), pd.Series(p["weights"])
        order = (cw - tw).abs().sort_values(ascending=False).index
        ui.list_rows([("⬆️" if cw[x] > tw[x] + 1e-4 else ("⬇️" if cw[x] < tw[x] - 1e-4 else "＝"), ui.esc(u.loc[x, "company"]),
                       f"{ui.pct(tw[x], 0)} → <b>{ui.pct(cw[x], 0)}</b> of the portfolio",
                       ui.inr_short(cw[x] * amt), f"{'+' if cw[x] >= tw[x] else '−'}{ui.inr_short(abs(cw[x] - tw[x]) * amt)}")
                      for x in order])
        rb = reg[which]
        bv = ctx.h(rb["risk"]["Historical"][k]["var"]) * amt
        av = ctx.h(rb["test2"]["var_after"]["Historical"][k]["var"]) * amt
        ui.compare(f"A bad day in {names[focus]}: today's weights vs rebalanced", bv, av, f"Today {ui.inr_short(bv)}",
                   f"Rebalanced {ui.inr_short(av)}")
        ui.section("All periods at a glance")
        tbl = pd.DataFrame({"Today": pd.Series(p["weights"])})
        for eid, reg_, ev in results:
            tbl[ui.short(ev)[:14]] = pd.Series(reg_[which]["test2"]["weights"])
        tbl.index = [u.loc[x, "company"].split(" ")[0][:12] for x in tbl.index]
        ui.show(CH.weights_heat(tbl))
        if boot:
            sig = [ui.short(ev) for eid, reg_, ev in results if reg_[which]["test2"]["turnover"] > boot[which]["turnover_p95"]]
            ui.verdict("🔁" if sig else "👍", "The mix depends on the market mood" if sig else "Your mix holds up",
                       (f"In {', '.join(sig)} the optimiser would genuinely rebuild Portfolio {which}." if sig else
                        f"The changes are no bigger than noise — no evidence Portfolio {which}'s weights are wrong for those times."))
    ui.next_button("Final verdict", "verdict")

if right is not None and results:
    with right:
        st.markdown(f"#### Portfolio {which}: optimum weights in every ticked period")
        full = pd.DataFrame({"Today": pd.Series(p["weights"])})
        for eid, reg_, ev in results:
            full[ev["name"]] = pd.Series(reg_[which]["test2"]["weights"])
        full.index = [f"{x} · {u.loc[x, 'company']}" for x in full.index]
        st.dataframe(full, width="stretch", column_config={c: st.column_config.NumberColumn(format="percent") for c in full.columns})
        rows = []
        for eid, reg_, ev in results:
            t2 = reg_[which]["test2"]
            rows.append({"Period": ev["name"], "Case": t2["case"], "Target": t2["target"], "R_max": t2["r_max"],
                         "Min-var return": t2["r_minvar"], "Optimal return": t2["ret"], "Optimal vol": t2["vol"],
                         "Turnover": t2["turnover"], "₹ to move": ui.inr(t2["turnover"] * amt),
                         "Noise p95": boot[which]["turnover_p95"] if boot else np.nan, "Efficiency gap": t2["efficiency_gap"],
                         "VaR before": ctx.h(reg_[which]["risk"]["Historical"][k]["var"]),
                         "VaR after": ctx.h(t2["var_after"]["Historical"][k]["var"])})
        df = pd.DataFrame(rows)
        st.dataframe(df, hide_index=True, width="stretch", column_config={
            c: st.column_config.NumberColumn(format="percent") for c in df.columns if c not in ("Period", "Case", "₹ to move")})
        st.caption(" ".join(f"**{v.split(' — ')[0]}**: {v.split(' — ')[1]}." for v in CASE.values()))
        PAL = [CH.CRISIS, CH.CALM, "#B45AC9", "#E0A33A", "#4BB5C1", "#8A8F98", "#6C7AE0"]
        if boot:
            for eid, reg_, ev in results:
                st.markdown(f"* {NR.test2_finding(ev['name'], p, reg_[which], boot[which]['turnover_p95'], amt)}")
        wt = pd.DataFrame({"Today": pd.Series(p["weights"])})
        for eid, reg_, ev in results:
            wt[ui.short(ev)[:16]] = pd.Series(reg_[which]["test2"]["weights"])
        ui.show(CH.weights_bars(wt, f"Portfolio {which}: weights the optimiser picks in each period"))
        ind = {"Today": p["industry_weights"]}
        ind.update({ui.short(ev)[:16]: reg_[which]["test2"]["industry_weights"] for eid, reg_, ev in results})
        ui.show(CH.industry_bars(ind, "Industry weights shift"))
        st.markdown("#### The problem solved in each period")
        st.latex(r"\min_w\; w^\top \Sigma_{\text{period}}\, w \quad \text{s.t.}\quad \mu_{\text{period}}^\top w \ge "
                 r"\min(\text{target},\, R_{\max,\text{period}}),\ \ \text{same bounds and industry caps}")
        st.latex(r"\text{target} = \mu_{\text{current}}^\top w_{\text{today}} = " + f"{p['target_return'] * 100:.1f}" + r"\%")
        st.caption("Efficiency gap = the extra volatility today's weights carried in that period compared with the efficient "
                   "portfolio that earned the same period return.")
        st.markdown("#### Frontiers: today vs each period")
        regimes = []
        for i, (eid, reg_, ev) in enumerate(results):
            t2 = reg_[which]["test2"]
            regimes.append((ui.short(ev)[:16], PAL[i % len(PAL)], t2["frontier"],
                            (t2["today_in_regime"]["vol"], t2["today_in_regime"]["ret"]), (t2["vol"], t2["ret"])))
        fig = CH.frontier(p, regimes=regimes, show_cloud=False, show_stocks=False,
                          title=f"Portfolio {which}: frontier per period, target {ui.pct(p['target_return'])}")
        fig.add_hline(y=p["target_return"], line=dict(color="#E6E9EF", dash="dot"), annotation_text="target return")
        ui.show(fig)
        st.markdown("#### Real shift or estimation noise?")
        if boot:
            b = boot[which]
            ui.show(CH.bootstrap_bands(p["symbols"], b["base"], b["band_lo"], b["band_hi"],
                                       [(f"{ui.short(ev)[:16]}-optimal", reg_[which]["test2"]["weights"], PAL[i % len(PAL)])
                                        for i, (eid, reg_, ev) in enumerate(results)],
                                       f"90% bands from {b['resamples']} bootstrap resamples of today's window"))
            outside = sorted({x for x in p["symbols"] for eid, reg_, ev in results
                              if not (b["band_lo"][x] - 1e-9 <= reg_[which]["test2"]["weights"][x] <= b["band_hi"][x] + 1e-9)})
            st.caption(f"Stocks whose period weight falls outside its noise band: {', '.join(outside) or 'none'}.")
            ui.show(CH.turnover_hist(b["turnover_noise"], b["turnover_p95"],
                                     [(ui.short(ev)[:12], reg_[which]["test2"]["turnover"], PAL[i % len(PAL)])
                                      for i, (eid, reg_, ev) in enumerate(results)]))
            st.caption("A shift is significant if its turnover is above the 95th percentile of turnover produced by noise alone "
                       f"(moving-block bootstrap of the latest 252 days, 5-day blocks, {b['resamples']} resamples).")
        ui.concept_box("Estimation error",
                       "Twelve months of prices are a small sample. Re-draw them slightly differently and the 'optimal' weights move — "
                       "sometimes a lot — even though nothing about the companies changed.",
                       "Markowitz weights are very sensitive to errors in μ (expected returns). The bootstrap re-solves the same "
                       "problem on resampled histories to measure that sensitivity.",
                       "If a crisis changes the weights by less than noise does, there is no evidence the allocation is wrong for that "
                       "regime; if by more, the weights are regime-dependent.",
                       "The grey bands, the turnover histogram and the 'beyond / within noise' labels on this page.")
