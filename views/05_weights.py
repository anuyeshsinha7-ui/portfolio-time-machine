"""Step 4 — Today: optimum weights, VaR and ES right now, and whether the portfolios are recommended as they are."""
import pandas as pd
import streamlit as st

from src import allocation as AL
from src import charts as CH
from src import config
from src import data as D
from src import engine as E
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
OBJ = {"A": "Highest expected return", "B": "Lowest variance", "C": "Highest Sharpe ratio"}
odds = round(1 / (1 - ctx.conf))
with left:
    ui.hero("Today", "Your portfolios right now", f"Weights and risk from the latest 12 months ({ctx.current['start']} → {ctx.current['end']})", "")
    ui.portfolio_badge()
    ui.section("Risk today", f"{ctx.conf:.0%} · {ctx.horizon}-day")
    ui.risk_explainer(ctx)
    tl = []
    for kk in ("A", "B", "C"):
        rk = ctx.current[kk]["risk"]["Historical"][k]
        am = ctx.amount(kk)
        tl += [(f"{kk} · VaR", ui.inr_short(ctx.h(rk["var"]) * am),
                f"{ui.pct(ctx.h(rk['var']))} · {ui.inr_short(am)} → {ui.inr_short(am * (1 - ctx.h(rk['var'])))}", kk.lower()),
               (f"{kk} · ES", ui.inr_short(ctx.h(rk["es"]) * am),
                f"{ui.pct(ctx.h(rk['es']))} · {ui.inr_short(am)} → {ui.inr_short(am * (1 - ctx.h(rk['es'])))}", kk.lower())]
    ui.tiles(tl)
    ui.section("Worked out from the last 12 months", f"{ctx.conf:.0%} · {ctx.horizon}-day")
    ui.list_rows([(ui.PLAN[kk][2], f"Portfolio {ui.NAMES[kk]}", ui.risk_text(ctx, ctx.current[kk], ctx.amount(kk)), "", "")
                  for kk in ("A", "B", "C")])
    ui.section("Is it recommended as it is?")
    ui.list_rows([("✅" if c["ok"] else "⚠️", c["name"], c["detail"], ui.chip("pass", "ok") if c["ok"] else ui.chip("check", "mid"), "")
                  for c in checks])
    if all(c["ok"] for c in checks):
        ui.verdict("👍", "Recommended as it is", "Both portfolios do what their labels promise today. Next, let's see if that "
                   "survives a crisis.")
    else:
        ui.verdict("🤔", "Recommended with caution", "Not every check passed — see above. The backtest shows how it would have "
                   "held up in real crises.")
    ui.section("Three ways to build it", "same limits for all")
    ui.list_rows([(ui.PLAN[kk][2], f"Portfolio {ui.NAMES[kk]}", OBJ[kk], ui.pct(ctx.P[kk]["expected_return"]),
                   f"swings {ui.pct(ctx.P[kk]['expected_vol'])} · Sharpe {ctx.P[kk]['sharpe']:.2f}") for kk in ("A", "B", "C")])
    ui.section("Your weights")
    which = st.segmented_control("Portfolio", ["A", "B", "C"], format_func=ui.NAMES.get, default="A", key="w_which", required=True)
    p = ctx.P[which]
    amt = ctx.amount(which)
    w = pd.Series(p["weights"]).sort_values(ascending=False)
    w = w[w > 1e-4]  # C may leave stocks out
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
    compare(f"VaR ({ctx.conf:.0%}, {ctx.horizon}-day): equal split vs our weights", eq_v * amt, op_v * amt,
            f"Equal {ui.inr_short(eq_v * amt)}", f"Ours {ui.inr_short(op_v * amt)}",
            {"A": "A chases the highest return, so its VaR is usually bigger than an equal split's.",
             "B": "B is built for the smallest swings, so its VaR should be smaller than an equal split's.",
             "C": "C balances return against risk (best Sharpe), so it sits between the two."}[which])
    for wmsg in p["constraints"]["warnings"]:
        ui.note(wmsg, "⚠️", "warn")
    if p.get("fell_back_to_minvar"):
        ui.note("No allowed mix beat the risk-free rate, so A uses the lowest-risk mix instead.", "⚠️", "warn")
    ui.next_button("Backtest it in uncertain times", "test1")

if right is not None:
    with right:
        st.markdown(f"#### Today's VaR and ES, worked out four ways ({ctx.conf:.0%}, {ctx.horizon}-day; ES also at 97.5%)")
        st.markdown(f"**VaR** at {ctx.conf:.0%} is the loss exceeded on only {1 - ctx.conf:.0%} of days. **ES** is the average loss on the days "
                    "that are worse than that. We work both out four ways and show the rupee amounts on your money.")
        rows = []
        for kk in ("A", "B", "C"):
            rk = ctx.current[kk]["risk"]
            for m in ("Historical", "Parametric normal", "Monte Carlo (Student-t)", "Cornish–Fisher"):
                rows.append({"Portfolio": kk, "Method": m, "VaR": ctx.h(rk[m][k]["var"]), "ES": ctx.h(rk[m][k]["es"]),
                             "ES 97.5%": ctx.h(rk[m]["0.975"]["es"]), "VaR ₹": ui.inr(ctx.h(rk[m][k]["var"]) * ctx.amount(kk)),
                             "ES ₹": ui.inr(ctx.h(rk[m][k]["es"]) * ctx.amount(kk)),
                             "Value after VaR ₹": ui.inr(ctx.amount(kk) * (1 - ctx.h(rk[m][k]["var"]))),
                             "Value after ES ₹": ui.inr(ctx.amount(kk) * (1 - ctx.h(rk[m][k]["es"])))})
        st.dataframe(ui.pct_df(pd.DataFrame(rows), ("VaR", "ES", "ES 97.5%")), hide_index=True, width="stretch")
        hcols = st.columns(3)
        for col, kk, colr in zip(hcols, ("A", "B", "C"), (CH.A, CH.B, CH.C)):
            r = ctx.current[kk]
            with col:
                ui.show(CH.returns_hist(r["returns"]["port"], r["risk"]["Historical"][k]["var"], r["risk"]["Historical"][k]["es"],
                                        colr, kk, ctx.conf))
        st.latex(r"\text{VaR}_c = -q_{1-c}(r_p) \qquad \text{ES}_c = -\mathbb{E}[\,r_p \mid r_p \le q_{1-c}\,] \qquad "
                 r"\text{₹} = \% \times \text{amount}")
        st.markdown(f"#### Parametric VaR step by step — the matrix method (Portfolio {ui.NAMES[which]}, latest 12 months, daily)")
        R_now, _ = E.window_returns(p["symbols"], ctx.current["start"], ctx.current["end"])
        ui.matrix_walkthrough(R_now, pd.Series(p["weights"]), ctx.conf, amt,
                              ctx.current[which]["risk"]["Parametric normal"][k]["var"], which)
        st.markdown("#### How we decide if it's recommended as it is")
        st.markdown(RC.RULES["as_is"])
        st.dataframe(pd.DataFrame([{"Check": c["name"], "Passed": c["ok"], "Numbers": c["detail"]} for c in checks]),
                     hide_index=True, width="stretch")
        st.markdown(f"#### Portfolio {which}: weights, rupees and number of shares")
        out = pd.DataFrame({"Company": u.loc[tb.index, "company"], "Industry": u.loc[tb.index, "industry"], "Weight": tb["weight"],
                            "₹ target": tb["target_rs"].map(ui.inr), "Price": tb["price"].map(lambda x: ui.inr(x, 2)),
                            "Shares": tb["shares"], "₹ invested": tb["invested_rs"].map(ui.inr), "Actual weight": tb["realised_weight"]})
        st.dataframe(ui.pct_df(out, ["Weight", "Actual weight"]), width="stretch")
        st.caption(f"Shares = weight × amount ÷ latest price, rounded down to a whole number. Cash left over: {ui.inr(alloc['cash'])}. "
                   f"Smallest amount that works: {ui.inr(alloc['min_sensible'])}.")
        rows = []
        for nm, blk in (("Equal weights (before)", vb["equal"]), ("Best weights (after)", vb["optimised"])):
            for m in ("Historical", "Parametric normal", "Monte Carlo (Student-t)", "Cornish–Fisher"):
                rows.append((nm, m, ui.pct(ctx.h(blk[m][k]["var"]), 2), ui.pct(ctx.h(blk[m][k]["es"]), 2)))
        st.markdown(f"#### VaR with equal weights vs the best weights ({ctx.conf:.0%}, {ctx.horizon}-day)")
        st.dataframe(pd.DataFrame(rows, columns=["Weights", "Method", "VaR", "ES"]), hide_index=True, width="stretch")
        st.markdown("#### How the weights are chosen")
        st.markdown("Three portfolios, three goals. **A (Bold)** maximises the expected return. **B (Steady)** minimises the "
                    "variance. **C (Optimum)** maximises the Sharpe ratio, the return earned for each unit of risk, using A's and "
                    "B's stocks together. All three follow the same limits:")
        st.latex(r"\textbf{A: } \max_w\; \mu^\top w \qquad \textbf{B: } \min_w\; w^\top\Sigma w \qquad "
                 r"\textbf{C: } \max_w \frac{\mu^\top w - r_f}{\sqrt{w^\top\Sigma w}}")
        st.latex(r"\text{s.t. } \sum_i w_i = 1,\quad " + f"{config.W_MIN:.2f}" + r"\le w_i \le " + f"{config.W_MAX:.2f}" +
                 r",\quad \sum_{i\in\text{industry}} w_i \le " + f"{config.INDUSTRY_MAX:.2f}")
        st.caption(f"C holds {len(ctx.P['C']['symbols'])} stocks, so its minimum weight is {config.C_W_MIN:.0%}: with a 2% floor, "
                   f"{len(ctx.P['C']['symbols'])} × 2% = {len(ctx.P['C']['symbols']) * 0.02:.0%} of the money would be locked into an "
                   "equal split. A's maximum return is a straight-line problem (a linear program), so its answer sits at a corner: "
                   "the minimum in every stock and as much as the limits allow in the few with the best past return.")
        st.dataframe(ui.pct_df(pd.DataFrame([{"Portfolio": ui.NAMES[kk], "Goal": OBJ[kk], "Stocks held": int(sum(v > 1e-4 for v in ctx.P[kk]["weights"].values())),
                                    "Expected return": ctx.P[kk]["expected_return"], "Volatility": ctx.P[kk]["expected_vol"],
                                    "Sharpe": round(ctx.P[kk]["sharpe"], 2)} for kk in ("A", "B", "C")]), ("Expected return", "Volatility")), hide_index=True, width="stretch")
        st.markdown(f"μ is the average daily return × 252. Σ is how the stocks move together (covariance) × 252. r_f is "
                    f"{config.RISK_FREE_RATE:.2%}, the 91-day Treasury bill rate. We solve it with SciPy's SLSQP method, starting "
                    f"from several points. After solving, we check every limit again, and our tests compare the answer with cvxpy.")
        ui.show(CH.frontier(p, title=f"Portfolio {which}: the best mixes of these stocks (latest 12 months)"))
        fr = p["frontier"]
        st.caption(f"The line starts at {ui.pct(fr['r_min'])}, the return of the least risky mix, and ends at {ui.pct(fr['r_max'])}, "
                   f"the highest return the limits allow. In between we found the least risky mix for {len(fr['rets'])} target "
                   f"returns. Our pick: return {ui.pct(p['expected_return'])}, volatility {ui.pct(p['expected_vol'])}, "
                   f"Sharpe {p['sharpe']:.2f}.")
        ui.concept_box("Efficient frontier",
                       "For each level of return, one mix of the stocks has the least risk. Join up those best mixes and you get "
                       "the frontier. Any mix below the line gives you less return for the same risk.",
                       "The set of portfolios solving min wᵀΣw subject to μᵀw = R, for R between R_min and R_max.",
                       "It only makes sense to pick a mix on the line. Where on the line depends on how much risk you are happy with.",
                       "The chart above (grey dots are random mixes, the line is the frontier) and the frontier chart on the Rebalance screen.")
        ui.concept_box("Sharpe ratio",
                       "How much return you get for each unit of risk, after taking away what a safe Treasury bill pays.",
                       "Sharpe = (μ_p − r_f) ÷ σ_p.",
                       "It lets you compare portfolios fairly. A 30% return with 40% volatility can be worse than 15% with 10%.",
                       "Portfolio C is built to get the highest Sharpe ratio (the star on its chart).",
                       latex=r"\text{Sharpe} = \frac{\mu_p - r_f}{\sigma_p}")
