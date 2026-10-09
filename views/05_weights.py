"""Step 4 — Today: optimum weights, VaR and ES right now, and whether the portfolios are recommended as they are."""
import pandas as pd
import streamlit as st

from src import allocation as AL
from src import charts as CH
from src import config
from src import data as D
from src import recommend as RC
from src import ui
from src.ui import compare

ctx = ui.context()
k = ctx.ck()
left, right = ui.split()
prices = D.latest_prices()
u = ui.universe_table()
which = None

checks = RC.as_is_checks(ctx.evidence, ctx.P, ctx.current)
odds = round(1 / (1 - ctx.conf))
with left:
    ui.hero("Today", "Your portfolios right now", f"Weights and risk from the latest 12 months ({ctx.current['start']} → {ctx.current['end']})", "")
    ui.portfolio_badge()
    ui.section("Risk today", f"{ctx.horizon}-day · 1 in {odds} days")
    tl = []
    for kk in ("A", "B"):
        rk = ctx.current[kk]["risk"]["Historical"][k]
        am = ctx.amount(kk)
        tl += [(f"{kk} · a bad day could cost", ui.inr_short(ctx.h(rk["var"]) * am), f"VaR {ui.pct(ctx.h(rk['var']))}", kk.lower()),
               (f"{kk} · worst days average", ui.inr_short(ctx.h(rk["es"]) * am), f"ES {ui.pct(ctx.h(rk['es']))}", kk.lower())]
    ui.tiles(tl)
    ui.section("Is it recommended as it is?")
    ui.list_rows([("✅" if c["ok"] else "⚠️", c["name"], c["detail"], ui.chip("pass", "ok") if c["ok"] else ui.chip("check", "mid"), "")
                  for c in checks])
    if all(c["ok"] for c in checks):
        ui.verdict("👍", "Recommended as it is", "Both portfolios do what their labels promise today. Next, let's see if that "
                   "survives a crisis.")
    else:
        ui.verdict("🤔", "Recommended with caution", "Not every check passed — see above. The backtest shows how it would have "
                   "held up in real crises.")
    ui.section("Your weights")
    which = st.segmented_control("Portfolio", ["A", "B"], format_func=lambda x: "A · Bold" if x == "A" else "B · Steady",
                                 default="A", key="w_which", required=True)
    p = ctx.P[which]
    amt = ctx.amount(which)
    w = pd.Series(p["weights"]).sort_values(ascending=False)
    alloc = AL.allocate(w, prices, amt)
    tb = alloc["table"]
    ui.hero(f"Your shopping list · Portfolio {which}", ui.inr_short(alloc["invested"]),
            f"invested across {int((tb['shares'] > 0).sum())} companies · {ui.inr(alloc['cash'])} left as cash", which.lower())
    ui.list_rows([("🏢", ui.esc(u.loc[sym, "company"]), f"{int(r['shares']):,} shares × {ui.inr(r['price'], 2)}",
                   ui.inr(r["invested_rs"]), f"{r['weight']:.0%} of the plan") for sym, r in tb.iterrows()])
    if alloc["unbuyable"]:
        ui.note(f"{ui.inr(amt)} is too small to buy even one share of <b>{', '.join(alloc['unbuyable'])}</b>. "
                f"Invest at least <b>{ui.inr(alloc['min_sensible'])}</b> to own every company.", "⚠️", "warn")
    ui.tiles([("Expected return a year", ui.pct(p["expected_return"]), "with these weights", which.lower()),
              ("Ups and downs a year", ui.pct(p["expected_vol"]), "volatility", which.lower())])
    vb = p["var_before_after"]
    eq_v, op_v = ctx.h(vb["equal"]["Historical"][k]["var"]), ctx.h(vb["optimised"]["Historical"][k]["var"])
    compare(f"A bad day (1 in {round(1 / (1 - ctx.conf))}): equal split vs our weights", eq_v * amt, op_v * amt,
            f"Equal {ui.inr_short(eq_v * amt)}", f"Ours {ui.inr_short(op_v * amt)}",
            "B is built for the smallest swings; A for the best return per unit of risk, so its bad day can be a little bigger.")
    for wmsg in p["constraints"]["warnings"]:
        ui.note(wmsg, "⚠️", "warn")
    if p.get("fell_back_to_minvar"):
        ui.note("No allowed mix beat the risk-free rate, so A uses the lowest-risk mix instead.", "⚠️", "warn")
    ui.next_button("Backtest it in uncertain times", "test1")

if right is not None:
    with right:
        st.markdown(f"#### VaR and ES today, four methods ({ctx.conf:.0%}, {ctx.horizon}-day; ES also at 97.5%)")
        rows = []
        for kk in ("A", "B"):
            rk = ctx.current[kk]["risk"]
            for m in ("Historical", "Parametric normal", "Monte Carlo (Student-t)", "Cornish–Fisher"):
                rows.append({"Portfolio": kk, "Method": m, "VaR": ctx.h(rk[m][k]["var"]), "ES": ctx.h(rk[m][k]["es"]),
                             "ES 97.5%": ctx.h(rk[m]["0.975"]["es"]), "VaR ₹": ui.inr(ctx.h(rk[m][k]["var"]) * ctx.amount(kk)),
                             "ES ₹": ui.inr(ctx.h(rk[m][k]["es"]) * ctx.amount(kk))})
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch",
                     column_config={c: st.column_config.NumberColumn(format="percent") for c in ("VaR", "ES", "ES 97.5%")})
        h1, h2 = st.columns(2)
        for col, kk, colr in ((h1, "A", CH.A), (h2, "B", CH.B)):
            r = ctx.current[kk]
            with col:
                ui.show(CH.returns_hist(r["returns"]["port"], r["risk"]["Historical"][k]["var"], r["risk"]["Historical"][k]["es"],
                                        colr, kk, ctx.conf))
        st.latex(r"\text{VaR}_c = -q_{1-c}(r_p) \qquad \text{ES}_c = -\mathbb{E}[\,r_p \mid r_p \le q_{1-c}\,] \qquad "
                 r"\text{₹} = \% \times \text{amount}")
        st.markdown("#### Recommended as it is? — the rule")
        st.markdown(RC.RULES["as_is"])
        st.dataframe(pd.DataFrame([{"Check": c["name"], "Passed": c["ok"], "Numbers": c["detail"]} for c in checks]),
                     hide_index=True, width="stretch")
        st.markdown(f"#### Portfolio {which}: weights, rupees and whole shares")
        out = pd.DataFrame({"Company": u.loc[tb.index, "company"], "Industry": u.loc[tb.index, "industry"], "Weight": tb["weight"],
                            "₹ target": tb["target_rs"].map(ui.inr), "Price": tb["price"].map(lambda x: ui.inr(x, 2)),
                            "Shares": tb["shares"], "₹ invested": tb["invested_rs"].map(ui.inr), "Realised weight": tb["realised_weight"]})
        st.dataframe(out, width="stretch", column_config={"Weight": st.column_config.NumberColumn(format="percent"),
                                                           "Realised weight": st.column_config.NumberColumn(format="percent")})
        st.caption(f"Shares = ⌊weight × amount ÷ latest price⌋; leftover cash {ui.inr(alloc['cash'])}; minimum sensible amount "
                   f"{ui.inr(alloc['min_sensible'])}.")
        rows = []
        for nm, blk in (("Equal weights (before)", vb["equal"]), ("Optimised weights (after)", vb["optimised"])):
            for m in ("Historical", "Parametric normal", "Monte Carlo (Student-t)", "Cornish–Fisher"):
                rows.append((nm, m, ui.pct(ctx.h(blk[m][k]["var"]), 2), ui.pct(ctx.h(blk[m][k]["es"]), 2)))
        st.markdown(f"#### VaR before vs after optimising ({ctx.conf:.0%}, {ctx.horizon}-day)")
        st.dataframe(pd.DataFrame(rows, columns=["Weights", "Method", "VaR", "ES"]), hide_index=True, width="stretch")
        st.markdown("#### The optimisation problem")
        st.latex(r"\textbf{A: } \max_w \frac{\mu^\top w - r_f}{\sqrt{w^\top\Sigma w}} \qquad \textbf{B: } \min_w\; w^\top\Sigma w")
        st.latex(r"\text{s.t. } \sum_i w_i = 1,\quad " + f"{config.W_MIN:.2f}" + r"\le w_i \le " + f"{config.W_MAX:.2f}" +
                 r",\quad \sum_{i\in\text{industry}} w_i \le " + f"{config.INDUSTRY_MAX:.2f}")
        st.markdown(f"μ = mean daily simple return × 252; Σ = sample covariance × 252; r_f = {config.RISK_FREE_RATE:.2%} "
                    f"(91-day T-bill). Solved with SciPy SLSQP from several starting points; every constraint is re-checked after the solve "
                    f"and cross-checked against cvxpy in the test suite.")
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
