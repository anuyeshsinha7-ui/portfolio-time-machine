"""Page 4 — The risk call: why A is high risk and B is low risk (brief §8.4, §6.3)."""
import numpy as np
import pandas as pd
import streamlit as st

from src import charts as CH
from src.ui import compare
from src import narrative as NR
from src import ui

ctx = ui.context()
ev = ctx.evidence
left, right = ui.split()
a, b = ev["A"], ev["B"]
vr = ev["vol_ratio"]

with left:
    ui.hero("Why A is the bold one", f"{vr['ratio']:.1f}× the ups and downs",
            "Portfolio A swings about this much more than B — measured over the last 3 years", "a")
    compare("If the market moves 10%, the portfolio tends to move…", a["weighted_beta"], b["weighted_beta"],
            ui.pct(a["weighted_beta"] * 0.10, 0), ui.pct(b["weighted_beta"] * 0.10, 0), "Based on beta: how strongly each rides the market.")
    compare("A typical bad year could swing your money by…", a["portfolio_vol"] * ctx.amount_a, b["portfolio_vol"] * ctx.amount_b,
            ui.inr_short(a["portfolio_vol"] * ctx.amount_a), ui.inr_short(b["portfolio_vol"] * ctx.amount_b),
            f"One standard deviation of yearly returns ({ui.pct(a['portfolio_vol'])} vs {ui.pct(b['portfolio_vol'])}).")
    compare("Biggest fall from a peak in the last 3 years", a["max_drawdown"] * ctx.amount_a, b["max_drawdown"] * ctx.amount_b,
            ui.inr_short(a["max_drawdown"] * ctx.amount_a), ui.inr_short(b["max_drawdown"] * ctx.amount_b))
    compare("How much the stocks move together", a["avg_pairwise_corr"], b["avg_pairwise_corr"],
            f"{a['avg_pairwise_corr']:.2f}", f"{b['avg_pairwise_corr']:.2f}", "Lower = better spread out (0 = independent, 1 = in lockstep).")
    if vr["significant"]:
        ui.note(f"<b>Not luck.</b> Re-running the last three years {vr['resamples']} times, A stays {vr['lo']:.1f}–{vr['hi']:.1f}× "
                "bumpier than B in 95% of cases.", "✅", "good")
    else:
        ui.note(f"<b>Not clear-cut.</b> Re-running history, the ratio ranges {vr['lo']:.1f}–{vr['hi']:.1f}×, which includes 1.", "⚠️", "warn")
    ui.section("Where your money goes", "by industry")
    ui.show(CH.industry_bars({"A · Bold": ctx.P["A"]["industry_weights"], "B · Steady": ctx.P["B"]["industry_weights"]}))
    big_a = a["cap_mix"].get("Large cap", 0)
    big_b = b["cap_mix"].get("Large cap", 0)
    ui.tiles([("Large companies in A", ui.pct(big_a, 0), "Nifty 100 members", "a"), ("Large companies in B", ui.pct(big_b, 0), "Nifty 100 members", "b")])

if right is not None:
    with right:
        st.caption(f"The last three years, {ev['window']['start']} to {ev['window']['end']} (the same period we use for the labels).")
        st.markdown(f"<div class='ptm-verdict'>{NR.call_finding(ev, ctx.amount_a, ctx.amount_b)}</div>", unsafe_allow_html=True)
        rows = [("Beta: weighted average of the stocks (Σwβ)", f"{a['weighted_beta']:.2f}", f"{b['weighted_beta']:.2f}"),
                ("Beta: measured on the portfolio itself", f"{a['portfolio_beta']:.2f}", f"{b['portfolio_beta']:.2f}"),
                ("Volatility √(wᵀΣw)", ui.pct(a["portfolio_vol"]), ui.pct(b["portfolio_vol"])),
                ("Biggest fall", ui.pct(a["max_drawdown"]), ui.pct(b["max_drawdown"])),
                ("Average correlation between pairs of stocks", f"{a['avg_pairwise_corr']:.2f}", f"{b['avg_pairwise_corr']:.2f}"),
                ("Yearly return / Sharpe", f"{ui.pct(a['ann_return'])} / {a['sharpe']:.2f}", f"{ui.pct(b['ann_return'])} / {b['sharpe']:.2f}"),
                ("Large-cap share", ui.pct(a["cap_mix"].get("Large cap", 0), 0), ui.pct(b["cap_mix"].get("Large cap", 0), 0)),
                ("Stocks with the right label", f"{sum(v == 'High risk' for v in a['stock_labels'].values())}/{len(a['stock_labels'])}",
                 f"{sum(v == 'Low risk' for v in b['stock_labels'].values())}/{len(b['stock_labels'])}"),
                ("A's volatility ÷ B's, with 95% bootstrap range", f"{vr['ratio']:.2f} ({vr['lo']:.2f} to {vr['hi']:.2f})", "")]
        st.dataframe(pd.DataFrame(rows, columns=["Evidence", "A", "B"]), hide_index=True, width="stretch")
        st.markdown("#### Working out the portfolio's beta")
        st.latex(r"\beta_p = \sum_i w_i\,\beta_i")
        for k, e in (("A", a), ("B", b)):
            w = pd.Series(ctx.P[k]["weights"])
            bt = pd.Series(e["stock_betas"])
            terms = " + ".join(f"{w[s]:.2f}\\times{bt[s]:.2f}" for s in w.index[:4])
            st.latex(rf"\beta_{k} = {terms} + \dots = {e['weighted_beta']:.2f}")
        st.markdown("#### Working out the portfolio's volatility")
        st.latex(r"\sigma_p = \sqrt{w^\top \Sigma\, w}\,, \quad \Sigma = \text{annualised covariance of daily returns}")
        for k, e in (("A", a), ("B", b)):
            st.latex(rf"\sigma_{k} = \sqrt{{w_{k}^\top \Sigma_{k}\, w_{k}}} = {e['portfolio_vol']:.4f} = {e['portfolio_vol'] * 100:.1f}\%")
        st.caption("Spreading money across stocks makes the portfolio's volatility well below the weighted average of the "
                   "stocks' own volatilities: "
                   f"A {ui.pct(sum(ctx.P['A']['weights'][s] * a['stock_vols'][s] for s in a['stock_vols']))} → {ui.pct(a['portfolio_vol'])}, "
                   f"B {ui.pct(sum(ctx.P['B']['weights'][s] * b['stock_vols'][s] for s in b['stock_vols']))} → {ui.pct(b['portfolio_vol'])}.")
        tabs = st.tabs(["How A's stocks move together", "How B's stocks move together", "A's volatility ÷ B's"])
        with tabs[0]:
            ui.show(CH.corr_heatmap(a["corr"], ctx.P["A"]["symbols"], f"Portfolio A: average correlation {a['avg_pairwise_corr']:.2f}", CH.A))
        with tabs[1]:
            ui.show(CH.corr_heatmap(b["corr"], ctx.P["B"]["symbols"], f"Portfolio B: average correlation {b['avg_pairwise_corr']:.2f}", CH.B))
        with tabs[2]:
            if vr.get("draws"):
                ui.show(CH.ratio_hist(vr["draws"], vr["lo"], vr["hi"], vr["ratio"]))
            st.caption("We reshuffle the data in 5-day blocks, using the same dates for both portfolios, so they stay matched "
                       "day by day and calm or stormy stretches stay together.")
        ui.concept_box("Diversification",
                       "Owning many stocks that don't all fall on the same day gives a smoother ride than owning any one of "
                       "them. Don't put all your eggs in one basket.",
                       "Portfolio variance is wᵀΣw. Because the stocks are not perfectly correlated (correlation below 1), σ_p is "
                       "smaller than the weighted average of the stocks' own volatilities.",
                       "You get less risk for the same expected return. It works less well in a crisis, when stocks start moving "
                       "together.",
                       "The correlation charts, the σ_p sum above, and 'Correlations in a crisis' on the Backtest screen.")
