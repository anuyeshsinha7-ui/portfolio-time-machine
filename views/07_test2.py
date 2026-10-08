"""Page 7 — Time-travel test #2: would the optimiser still pick our weights? (brief §8.7, §6.9)."""
import pandas as pd
import streamlit as st

from src import charts as CH
from src import narrative as NR
from src import ui

left, right = ui.split()
with left:
    ui.hero("Rebuild check", "Would we change your portfolio?",
            "We ask the optimiser to hit today's expected return using a past period's data", "")
ui.event_selectors("t2")
ctx = ui.context()
k = ctx.ck()
boot = ctx.bootstrap()
CASE = {"reachable": "Reachable — the portfolio that hits today's target return with the least risk",
        "below_minvar": "Target below that period's minimum-variance return — the optimiser picks minimum variance (beats the target with less risk)",
        "unreachable": "Unreachable in that period — the closest it gets is the highest return the constraints allow"}
PLAIN = {"reachable": "could still hit today's target return", "below_minvar": "beats today's target with less risk",
         "unreachable": "can't reach today's target return"}
u = ui.universe_table()

with left:
    which = st.segmented_control("Portfolio", ["A", "B"], format_func=lambda x: "A · Bold" if x == "A" else "B · Steady",
                                 default="A", key="t2_which", required=True)
    p = ctx.P[which]
    amt = ctx.amount(which)
    regs = {"Today": ctx.current[which], "Crisis": ctx.crisis[which], "Calm": ctx.calm[which]}
    ui.tiles([("Today's target return", ui.pct(p["target_return"]), "a year, with today's weights", which.lower()),
              ("Your amount", ui.inr_short(amt), f"Portfolio {which}", which.lower())])
    rows = []
    for nm, ev in (("Crisis", ctx.crisis_ev), ("Calm", ctx.calm_ev)):
        t2 = regs[nm]["test2"]
        if boot:
            real = t2["turnover"] > boot[which]["turnover_p95"]
            c = ui.chip("real change", "bad") if real else ui.chip("just noise", "ok")
        else:
            c = ui.chip("run check", "grey")
        rows.append(("🌪️" if nm == "Crisis" else "🌤️", ui.esc(ui.short(ev)),
                     f"Optimiser {PLAIN[t2['case']]} · move {ui.pct(t2['turnover'], 0)} of the money", f"{ui.inr_short(t2['turnover'] * amt)}", c))
    ui.section("Money you'd need to move")
    ui.list_rows(rows)
    if boot:
        ui.note(f"Even with no change in the market, random noise in 12 months of prices can shuffle up to "
                f"<b>{ui.pct(boot[which]['turnover_p95'], 0)}</b> ({ui.inr_short(boot[which]['turnover_p95'] * amt)}) of this portfolio. "
                "Only moves bigger than that count as a real change.", "🎲")
    else:
        if st.button("Run the noise check", width="stretch"):
            ui.compute_bootstrap(ctx)
            st.rerun()
    cw = pd.Series(regs["Crisis"]["test2"]["weights"])
    tw = pd.Series(p["weights"])
    d = (cw - tw).abs().sort_values(ascending=False).head(5)
    ui.section("Biggest changes in the crash", "today → crash-optimal")
    ui.list_rows([("⬆️" if cw[s_] > tw[s_] else "⬇️", ui.esc(u.loc[s_, "company"]), f"{ui.pct(tw[s_], 0)} → {ui.pct(cw[s_], 0)} of the portfolio",
                   f"{'+' if cw[s_] > tw[s_] else '−'}{ui.inr_short(abs(cw[s_] - tw[s_]) * amt)}", "") for s_ in d.index])
    r = regs["Crisis"]
    bv = ctx.h(r["risk"]["Historical"][k]["var"]) * amt
    av = ctx.h(r["test2"]["var_after"]["Historical"][k]["var"]) * amt
    ui.compare(f"A bad day in the crash (1 in {round(1 / (1 - ctx.conf))}): our weights vs rebuilt", bv, av,
               f"Ours {ui.inr_short(bv)}", f"Rebuilt {ui.inr_short(av)}")
    if boot:
        sig = [nm for nm in ("Crisis", "Calm") if regs[nm]["test2"]["turnover"] > boot[which]["turnover_p95"]]
        ui.verdict("🔁" if sig else "👍", "The mix depends on the market mood" if sig else "Your mix holds up",
                   (f"In the {' and '.join(n.lower() for n in sig)} period the optimiser would genuinely rebuild Portfolio {which}."
                    if sig else f"The changes the optimiser wants are no bigger than noise — no evidence Portfolio {which}'s weights are wrong for those times."))

if right is not None:
    with right:
        if boot:
            for nm, ev in (("Crisis", ctx.crisis_ev), ("Calm", ctx.calm_ev)):
                st.markdown(f"* {NR.test2_finding(ev['name'], p, regs[nm], boot[which]['turnover_p95'], amt)}")
        wt = pd.DataFrame({"Today": pd.Series(p["weights"]), "Crisis": pd.Series(regs["Crisis"]["test2"]["weights"]),
                           "Calm": pd.Series(regs["Calm"]["test2"]["weights"])})
        ui.show(CH.weights_bars(wt, f"Portfolio {which}: weights the optimiser picks in each period"))
        ui.show(CH.industry_bars({"Today": p["industry_weights"], "Crisis": regs["Crisis"]["test2"]["industry_weights"],
                                  "Calm": regs["Calm"]["test2"]["industry_weights"]}, "Industry weights shift"))
        rows = []
        for nm in ("Crisis", "Calm"):
            r_ = regs[nm]
            rows.append((nm, ui.pct(ctx.h(r_["risk"]["Historical"][k]["var"]), 2), ui.pct(ctx.h(r_["test2"]["var_after"]["Historical"][k]["var"]), 2),
                         ui.pct(ctx.h(r_["risk"]["Historical"][k]["es"]), 2), ui.pct(ctx.h(r_["test2"]["var_after"]["Historical"][k]["es"]), 2),
                         ui.pct(r_["test2"]["turnover"]), ui.inr(r_["test2"]["turnover"] * amt)))
        st.markdown(f"#### VaR and ES before (today's weights) and after (period-optimal), {ctx.conf:.0%}, {ctx.horizon}-day")
        st.dataframe(pd.DataFrame(rows, columns=["Period", "VaR before", "VaR after", "ES before", "ES after", "Turnover", "Turnover ₹"]),
                     hide_index=True, width="stretch")
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
        fig.add_hline(y=p["target_return"], line=dict(color="#E6E9EF", dash="dot"), annotation_text="target return")
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
