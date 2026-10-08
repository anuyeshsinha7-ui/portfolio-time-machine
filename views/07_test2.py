"""Page 7 — Time-travel test #2: would the optimiser still pick our weights? (brief §8.7, §6.9)."""
import pandas as pd
import streamlit as st

from src import charts as CH
from src import narrative as NR
from src import ui

ui.page_header("test2", "Test #2 — would the optimiser still pick our weights?",
               "We take the return today's portfolio expects and ask Markowitz to hit that same return using each period's data. "
               "If the answer is very different, our weights depend on the times we live in.")
ui.event_selectors("t2")
ctx = ui.context()
ui.story_cards(ctx)
k = ctx.ck()
left, right = ui.split()
boot = ctx.bootstrap()
CASE = {"reachable": "Reachable — the portfolio that hits today's target return with the least risk",
        "below_minvar": "Target below that period's minimum-variance return — the optimiser picks minimum variance (beats the target with less risk)",
        "unreachable": "Unreachable in that period — the closest it gets is the highest return the constraints allow"}

with left:
    which = st.radio("Portfolio", ["A", "B"], horizontal=True, key="t2_which")
    p = ctx.P[which]
    amt = ctx.amount(which)
    regs = {"Today": ctx.current[which], "Crisis": ctx.crisis[which], "Calm": ctx.calm[which]}
    st.markdown(f"**Target return** (what today's weights expect): **{ui.pct(p['target_return'])}** a year.")
    wt = pd.DataFrame({"Today": pd.Series(p["weights"]),
                       "Crisis": pd.Series(regs["Crisis"]["test2"]["weights"]),
                       "Calm": pd.Series(regs["Calm"]["test2"]["weights"])})
    ui.show(CH.weights_bars(wt, f"Portfolio {which}: weights the optimiser picks in each period"))
    st.markdown("#### Industry weights shift")
    ui.show(CH.industry_bars({"Today": p["industry_weights"], "Crisis": regs["Crisis"]["test2"]["industry_weights"],
                              "Calm": regs["Calm"]["test2"]["industry_weights"]}))
    st.markdown("#### How much would you have to trade?")
    c1, c2 = st.columns(2)
    for col, nm in ((c1, "Crisis"), (c2, "Calm")):
        t = regs[nm]["test2"]
        sig = boot is not None and t["turnover"] > boot[which]["turnover_p95"]
        col.metric(f"Turnover to the {nm.lower()}-optimal weights", ui.pct(t["turnover"], 0),
                   f"{ui.inr_short(t['turnover'] * amt)} of your {ui.inr_short(amt)}", delta_color="off")
        col.caption(CASE[t["case"]].split(" — ")[0] + (" · beyond noise" if sig else (" · within noise" if boot else "")))
    st.markdown(f"#### Money at risk on a bad day — before vs after re-optimising ({ctx.conf:.0%}, {ctx.horizon}-day, historical)")
    rows = []
    for nm in ("Crisis", "Calm"):
        r = regs[nm]
        bv, be = ctx.h(r["risk"]["Historical"][k]["var"]), ctx.h(r["risk"]["Historical"][k]["es"])
        av, ae = ctx.h(r["test2"]["var_after"]["Historical"][k]["var"]), ctx.h(r["test2"]["var_after"]["Historical"][k]["es"])
        rows.append((nm, ui.inr(bv * amt), ui.inr(av * amt), ui.inr(be * amt), ui.inr(ae * amt)))
    st.dataframe(pd.DataFrame(rows, columns=["Period", "VaR today's weights", "VaR period-optimal", "ES today's weights", "ES period-optimal"]),
                 hide_index=True, width="stretch")
    st.markdown("#### Plain verdict")
    if boot:
        for nm, ev in (("Crisis", ctx.crisis_ev), ("Calm", ctx.calm_ev)):
            st.markdown(f"* {NR.test2_finding(ev['name'], p, regs[nm], boot[which]['turnover_p95'], amt)}")
    else:
        st.info("For your own picks, the noise check (bootstrap) runs on demand.")
        if st.button(f"Run the noise check ({ui.config.BOOTSTRAP_RESAMPLES_BROWSER} resamples per portfolio)"):
            boot = ui.compute_bootstrap(ctx)
            st.rerun()

if right is not None:
    with right:
        st.markdown("#### The problem solved in each period")
        st.latex(r"\min_w\; w^\top \Sigma_{\text{period}}\, w \quad \text{s.t.}\quad \mu_{\text{period}}^\top w \ge "
                 r"\min(\text{target},\, R_{\max,\text{period}}),\ \ \text{same bounds and industry caps}")
        st.latex(r"\text{target} = \mu_{\text{current}}^\top w_{\text{today}} = " + f"{p['target_return'] * 100:.1f}" + r"\%")
        rows = []
        for nm in ("Crisis", "Calm", "Today"):
            t = regs[nm]["test2"]
            rows.append({"Period": nm, "Min-variance return": t["r_minvar"], "R_max": t["r_max"], "Case": t["case"],
                         "Optimal return": t["ret"], "Optimal volatility": t["vol"],
                         "Today's weights: return": t["today_in_regime"]["ret"], "Today's weights: volatility": t["today_in_regime"]["vol"],
                         "Efficiency gap": t["efficiency_gap"]})
        df = pd.DataFrame(rows)
        st.dataframe(df, hide_index=True, width="stretch",
                     column_config={c: st.column_config.NumberColumn(format="percent") for c in df.columns if c not in ("Period", "Case")})
        st.caption("Efficiency gap = the extra volatility today's weights carried in that period compared with the efficient "
                   "portfolio that earned the same period return. " + " ".join(f"**{v.split(' — ')[0]}**: {v.split(' — ')[1]}." for v in CASE.values()))
        st.markdown("#### Frontiers: today vs crisis vs calm")
        regimes = []
        for nm, col in (("crisis", CH.CRISIS), ("calm", CH.CALM)):
            t = regs[nm.title()]["test2"]
            regimes.append((nm, col, t["frontier"], (t["today_in_regime"]["vol"], t["today_in_regime"]["ret"]), (t["vol"], t["ret"])))
        fig = CH.frontier(p, regimes=regimes, show_cloud=False, show_stocks=False,
                          title=f"Portfolio {which}: frontier per period, target {ui.pct(p['target_return'])}")
        fig.add_hline(y=p["target_return"], line=dict(color="#1F2430", dash="dot"), annotation_text="target return")
        ui.show(fig)
        st.markdown("#### Real shift or estimation noise?")
        if boot:
            b = boot[which]
            ui.show(CH.bootstrap_bands(p["symbols"], b["base"], b["band_lo"], b["band_hi"],
                                       [("Crisis-optimal", regs["Crisis"]["test2"]["weights"], CH.CRISIS),
                                        ("Calm-optimal", regs["Calm"]["test2"]["weights"], CH.CALM)],
                                       f"90% bands from {b['resamples']} bootstrap resamples of today's window"))
            outside = [s for s in p["symbols"] for nm in ("Crisis", "Calm")
                       if not (b["band_lo"][s] - 1e-9 <= regs[nm]["test2"]["weights"][s] <= b["band_hi"][s] + 1e-9)]
            st.caption(f"Stocks whose period weight falls outside its noise band: {', '.join(sorted(set(outside))) or 'none'}.")
            ui.show(CH.turnover_hist(b["turnover_noise"], b["turnover_p95"],
                                     [("crisis", regs["Crisis"]["test2"]["turnover"], CH.CRISIS),
                                      ("calm", regs["Calm"]["test2"]["turnover"], CH.CALM)]))
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
