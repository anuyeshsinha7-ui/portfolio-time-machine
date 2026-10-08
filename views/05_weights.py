"""Page 5 — Optimum weights today (brief §8.5, §6.6, §6.10)."""
import pandas as pd
import streamlit as st

from src import allocation as AL
from src import charts as CH
from src import config
from src import data as D
from src import ui

ctx = ui.context()
k = ctx.ck()
ui.page_header("weights", "Optimum weights for today",
               f"Optimised on the latest {config.REGIME_DAYS} trading days ({ctx.P['A']['window']['start']} → {ctx.P['A']['window']['end']}).")
left, right = ui.split()
prices = D.latest_prices()

with left:
    tabs = st.tabs(["Portfolio A", "Portfolio B"])
    for tab, key, amt in ((tabs[0], "A", ctx.amount_a), (tabs[1], "B", ctx.amount_b)):
        p = ctx.P[key]
        with tab:
            w = pd.Series(p["weights"]).sort_values(ascending=False)
            alloc = AL.allocate(w, prices, amt)
            tb = alloc["table"]
            u = ui.universe_table()
            out = pd.DataFrame({"Company": u.loc[tb.index, "company"], "Industry": u.loc[tb.index, "industry"],
                                "Weight": tb["weight"], "₹ target": tb["target_rs"].map(ui.inr),
                                "Price": tb["price"].map(lambda x: ui.inr(x, 2)), "Shares": tb["shares"],
                                "₹ invested": tb["invested_rs"].map(ui.inr), "Realised weight": tb["realised_weight"]})
            st.dataframe(out, width="stretch", column_config={"Weight": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=config.W_MAX),
                                                               "Realised weight": st.column_config.NumberColumn(format="percent")})
            c1, c2, c3 = st.columns(3)
            c1.metric("Invested", ui.inr_short(alloc["invested"]))
            c2.metric("Leftover cash", ui.inr(alloc["cash"]))
            c3.metric("Expected return", ui.pct(p["expected_return"]), help="Mean daily return × 252 with these weights, latest 12 months.")
            if alloc["unbuyable"]:
                st.warning(f"{ui.inr(amt)} is too small to buy even one share of: **{', '.join(alloc['unbuyable'])}** at its target weight. "
                           f"Their realised weight is 0%. The smallest amount that buys every stock is **{ui.inr(alloc['min_sensible'])}**.")
            for wmsg in p["constraints"]["warnings"]:
                st.warning(wmsg)
            if p.get("fell_back_to_minvar"):
                st.warning("No allowed portfolio beat the risk-free rate, so A falls back to the minimum-variance portfolio.")
            st.markdown(f"**Money at risk on a bad day — before vs after optimising** ({ctx.conf:.0%}, {ctx.horizon}-day, historical method)")
            vb = p["var_before_after"]
            rows = []
            for nm, blk in (("Equal weights (before)", vb["equal"]), ("Optimised weights (after)", vb["optimised"])):
                v, e = ctx.h(blk["Historical"][k]["var"]), ctx.h(blk["Historical"][k]["es"])
                rows.append((nm, ui.pct(v, 2), ui.inr(v * amt), ui.pct(e, 2), ui.inr(e * amt)))
            st.dataframe(pd.DataFrame(rows, columns=["Weights", "VaR %", "VaR ₹", "ES %", "ES ₹"]), hide_index=True, width="stretch")
            eq_v, op_v = vb["equal"]["Historical"][k]["var"], vb["optimised"]["Historical"][k]["var"]
            if key == "B":
                st.caption(f"B is optimised for the smallest swings, so its bad-day loss {'falls' if op_v < eq_v else 'barely changes'} "
                           f"({ui.pct(eq_v, 2)} → {ui.pct(op_v, 2)}).")
            else:
                st.caption(f"A is optimised for return per unit of risk, not for the smallest loss — its bad-day loss "
                           f"{'rises' if op_v > eq_v else 'falls'} ({ui.pct(eq_v, 2)} → {ui.pct(op_v, 2)}) in exchange for an expected return of {ui.pct(p['expected_return'])}.")

if right is not None:
    with right:
        st.markdown("#### The optimisation problem")
        st.latex(r"\textbf{A: } \max_w \frac{\mu^\top w - r_f}{\sqrt{w^\top\Sigma w}} \qquad \textbf{B: } \min_w\; w^\top\Sigma w")
        st.latex(r"\text{s.t. } \sum_i w_i = 1,\quad " + f"{config.W_MIN:.2f}" + r"\le w_i \le " + f"{config.W_MAX:.2f}" +
                 r",\quad \sum_{i\in\text{industry}} w_i \le " + f"{config.INDUSTRY_MAX:.2f}")
        st.markdown(f"μ = mean daily simple return × 252; Σ = sample covariance × 252; r_f = {config.RISK_FREE_RATE:.2%} "
                    f"(91-day T-bill). Solved with SciPy SLSQP from several starting points; every constraint is re-checked after the solve "
                    f"and cross-checked against cvxpy in the test suite.")
        which = st.radio("Frontier for", ["A", "B"], horizontal=True, key="w_frontier")
        p = ctx.P[which]
        ui.show(CH.frontier(p, title=f"Portfolio {which}: efficient frontier (latest 12 months)"))
        fr = p["frontier"]
        st.caption(f"R_min = {ui.pct(fr['r_min'])} (minimum-variance return); R_max = {ui.pct(fr['r_max'])} (highest return the constraints "
                   f"allow, a linear program); {len(fr['rets'])} target returns in between, each minimising variance. Chosen point: "
                   f"return {ui.pct(p['expected_return'])}, volatility {ui.pct(p['expected_vol'])}, Sharpe {p['sharpe']:.2f}.")
        ui.concept_box("Efficient frontier",
                       "For every level of return there is one mix of the stocks with the least risk. Join those best mixes and you get "
                       "the frontier — anything below it is leaving return on the table.",
                       "The set of portfolios solving min wᵀΣw subject to μᵀw = R, for R between R_min and R_max.",
                       "A sensible investor only picks portfolios on the frontier; where on it depends on how much risk they accept.",
                       "The chart above (grey dots are random portfolios, the line is the frontier) and the frontier overlays on Test #2.")
        ui.concept_box("Sharpe ratio",
                       "Return earned per unit of bumpiness, after subtracting what a risk-free Treasury bill pays.",
                       "Sharpe = (μ_p − r_f) ÷ σ_p.",
                       "It compares portfolios on a level field: a 30% return with 40% volatility can be worse than 15% with 10%.",
                       "Portfolio A is chosen to maximise it (the star on the frontier).",
                       latex=r"\text{Sharpe} = \frac{\mu_p - r_f}{\sigma_p}")
