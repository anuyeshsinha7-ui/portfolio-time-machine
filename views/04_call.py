"""Page 4 — The risk call: why A is high risk and B is low risk (brief §8.4, §6.3)."""
import numpy as np
import pandas as pd
import streamlit as st

from src import charts as CH
from src import narrative as NR
from src import ui

ctx = ui.context()
ev = ctx.evidence
ui.page_header("call", "The risk call: why A is high risk and B is low risk",
               f"Numbers from the trailing three years ({ev['window']['start']} → {ev['window']['end']}), the same window as the labels.")
left, right = ui.split()
a, b = ev["A"], ev["B"]
vr = ev["vol_ratio"]

with left:
    st.markdown(f"<div class='ptm-verdict'>{NR.call_finding(ev, ctx.amount_a, ctx.amount_b)}</div>", unsafe_allow_html=True)
    st.write("")
    rows = [("How much it moves with the market (weighted beta)", f"{a['weighted_beta']:.2f}", f"{b['weighted_beta']:.2f}"),
            ("How bumpy the ride is (volatility a year)", ui.pct(a["portfolio_vol"]), ui.pct(b["portfolio_vol"])),
            ("…in rupees, a typical bad year (1 standard deviation)", ui.inr_short(a["portfolio_vol"] * ctx.amount_a),
             ui.inr_short(b["portfolio_vol"] * ctx.amount_b)),
            ("Worst peak-to-trough fall in 3 years", ui.pct(a["max_drawdown"]), ui.pct(b["max_drawdown"])),
            ("…in rupees on your amount", ui.inr_short(a["max_drawdown"] * ctx.amount_a), ui.inr_short(b["max_drawdown"] * ctx.amount_b)),
            ("How alike the stocks move (average correlation)", f"{a['avg_pairwise_corr']:.2f}", f"{b['avg_pairwise_corr']:.2f}"),
            ("Share in large companies (Nifty 100)", ui.pct(a["cap_mix"].get("Large cap", 0), 0), ui.pct(b["cap_mix"].get("Large cap", 0), 0)),
            ("Stocks with a matching label", f"{sum(v == 'High risk' for v in a['stock_labels'].values())} of {len(a['stock_labels'])}",
             f"{sum(v == 'Low risk' for v in b['stock_labels'].values())} of {len(b['stock_labels'])}")]
    st.dataframe(pd.DataFrame(rows, columns=["Evidence", "Portfolio A", "Portfolio B"]), hide_index=True, width="stretch")
    sig = vr["significant"]
    st.html(f"<div class='ptm-card ptm-{'a' if sig else 'n'}'><h4>Is the difference real or luck?</h4>"
            f"<div class='big'>{vr['ratio']:.2f}× {ui.pill('statistically backed', 'ok') if sig else ui.pill('not significant', 'bad')}</div>"
            f"<div class='sub'>A's volatility ÷ B's. Re-drawing the last three years {vr['resamples']} times, the ratio stays between "
            f"<b>{vr['lo']:.2f}</b> and <b>{vr['hi']:.2f}</b> 95% of the time — {'entirely above 1, so A really is riskier.' if sig else 'the range includes 1.'}</div></div>")
    st.markdown("#### Industry weights")
    ui.show(CH.industry_bars({"Portfolio A": ctx.P["A"]["industry_weights"], "Portfolio B": ctx.P["B"]["industry_weights"]}))

if right is not None:
    with right:
        st.markdown("#### Portfolio beta, worked")
        st.latex(r"\beta_p = \sum_i w_i\,\beta_i")
        for k, e in (("A", a), ("B", b)):
            w = pd.Series(ctx.P[k]["weights"])
            bt = pd.Series(e["stock_betas"])
            terms = " + ".join(f"{w[s]:.2f}\\times{bt[s]:.2f}" for s in w.index[:4])
            st.latex(rf"\beta_{k} = {terms} + \dots = {e['weighted_beta']:.2f}")
        st.markdown("#### Portfolio volatility, worked")
        st.latex(r"\sigma_p = \sqrt{w^\top \Sigma\, w}\,, \quad \Sigma = \text{annualised covariance of daily returns}")
        for k, e in (("A", a), ("B", b)):
            st.latex(rf"\sigma_{k} = \sqrt{{w_{k}^\top \Sigma_{k}\, w_{k}}} = {e['portfolio_vol']:.4f} = {e['portfolio_vol'] * 100:.1f}\%")
        st.caption("Diversification shows up as σ_p being well below the weighted average of the stocks' own volatilities: "
                   f"A {ui.pct(sum(ctx.P['A']['weights'][s] * a['stock_vols'][s] for s in a['stock_vols']))} → {ui.pct(a['portfolio_vol'])}, "
                   f"B {ui.pct(sum(ctx.P['B']['weights'][s] * b['stock_vols'][s] for s in b['stock_vols']))} → {ui.pct(b['portfolio_vol'])}.")
        tabs = st.tabs(["Correlations A", "Correlations B", "Bootstrap σA/σB"])
        with tabs[0]:
            ui.show(CH.corr_heatmap(a["corr"], ctx.P["A"]["symbols"], f"Portfolio A — average {a['avg_pairwise_corr']:.2f}", CH.A))
        with tabs[1]:
            ui.show(CH.corr_heatmap(b["corr"], ctx.P["B"]["symbols"], f"Portfolio B — average {b['avg_pairwise_corr']:.2f}", CH.B))
        with tabs[2]:
            if vr.get("draws"):
                ui.show(CH.ratio_hist(vr["draws"], vr["lo"], vr["hi"], vr["ratio"]))
            st.caption("Moving-block bootstrap: 5-day blocks of the same dates are resampled for both portfolios, so the two stay "
                       "matched day by day and short-run clustering of volatility is kept.")
        ui.concept_box("Diversification",
                       "Owning ten stocks that don't all fall on the same day gives a smoother ride than any one of them — "
                       "like not putting all your eggs in one basket.",
                       "Portfolio variance is wᵀΣw. The off-diagonal covariances (correlations below 1) make σ_p smaller than the "
                       "weighted average of individual volatilities.",
                       "It is the only 'free lunch' in finance: less risk for the same expected return. It weakens in a crisis, when "
                       "correlations jump.",
                       "The correlation heatmaps, the σ_p calculation above, and 'Correlations in a crisis' on Test #1.")
