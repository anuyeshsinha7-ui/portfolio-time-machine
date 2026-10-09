"""Screen 1 — Home: the 30-second verdict (brief §8.1)."""
import streamlit as st

from src import config
from src import narrative as NR
from src import recommend as RC
from src import ui

ctx = ui.context()
s = st.session_state
left, right = ui.split()
A, B = ctx.P["A"], ctx.P["B"]
cr, cm, cur = ctx.crisis, ctx.calm, ctx.current
k = ctx.ck()
board = ctx.scoreboard()

with left:
    total = ctx.amount_a + ctx.amount_b
    ui.hero("Your money in two portfolios", ui.inr_short(total),
            f"A {ui.inr_short(ctx.amount_a)} · B {ui.inr_short(ctx.amount_b)} · prices as of {ctx.res['as_of']}")
    for key, p, amt in (("A", A, ctx.amount_a), ("B", B, ctx.amount_b)):
        var_today = ctx.h(cur[key]["risk"]["Historical"][k]["var"])
        fall = cr[key]["replay"]["largest_fall"]
        ui.plan_card(key, amt, [
            ("Expected return a year", ui.pct(p["expected_return"])),
            (f"A bad day today (1 in {round(1 / (1 - ctx.conf))})", f"−{ui.inr_short(var_today * amt)}"),
            (f"Worst fall in the {ui.short(ctx.crisis_ev)}", f"−{ui.inr_short(fall * amt)}"),
            ("Stocks · industries", f"{len(p['symbols'])} · {len(p['industry_weights'])}"),
        ])
    held = RC.label_holds(cr["A"], cr["B"])
    ui.section("The answer", "time-travel tests")
    n_held = sum(r["label_held"] for r in board) if board else None
    ui.verdict("✅" if held else "⚠️", "Bold stayed riskier — Steady stayed calmer" if held else "The labels did not hold",
               (f"Tested in {len(board)} real market events since 2007: Portfolio A was the riskier one in {n_held}. " if board else "")
               + f"In the {ui.short(ctx.crisis_ev)}, {ui.inr_short(ctx.amount_a)} in A fell to "
               f"<b>{ui.inr_short(cr['A']['replay']['low'] * ctx.amount_a)}</b>; in B to <b>{ui.inr_short(cr['B']['replay']['low'] * ctx.amount_b)}</b>.")
    ui.section("Explore")
    st.page_link(s["_pages"]["test1"], label="Travel back to a crash", icon="🌪️")
    st.page_link(s["_pages"]["pick"], label="Choose your own stocks", icon="🧺")
    st.page_link(s["_pages"]["verdict"], label="Which portfolio fits me?", icon="✅")
    st.page_link(s["_pages"]["start"], label="Change amount", icon="✏️")

if right is not None:
    with right:
        st.markdown("#### What the app tests")
        st.markdown(f"We build two portfolios of Nifty 500 stocks **today**. A is high risk (beta of 1 or more and volatility at or "
                    f"above the middle value). B is low risk. Then we send both back to real crises and calm periods. Prices are "
                    f"up to {ctx.res['as_of']}.")
        st.markdown("#### The three main findings (written from the numbers)")
        st.markdown(f"1. {NR.es_finding(ctx.crisis_ev['name'], cr['A'], cr['B'], ctx.amount_a, ctx.amount_b, held)}")
        st.markdown(f"2. {NR.replay_finding(ctx.crisis_ev['name'], cr['A'], cr['B'], cr['nifty'], ctx.amount_a, ctx.amount_b)}")
        boot = ctx.bootstrap()
        if boot:
            st.markdown(f"3. {NR.test2_finding(ctx.crisis_ev['name'], A, cr['A'], boot['A']['turnover_p95'], ctx.amount_a)}")
        st.markdown("#### How the numbers on the phone are worked out")
        st.markdown(f"* **Bad day today**: the 1-day historical Value at Risk at {ctx.conf:.0%}, using the latest 252 days, times your "
                    f"amount{' (multiplied by √10 for 10 days)' if ctx.horizon == 10 else ''}.\n"
                    "* **Worst fall**: the biggest drop in your rupee value if you bought on the first day of the crisis period and "
                    "held on.\n"
                    "* **Expected return**: the average daily return × 252, with today's weights.\n"
                    "* **'Stayed riskier'**: A's Expected Shortfall (99%) and volatility were both higher than B's.")
        st.markdown("#### Every step, from data to answer")
        ui.flowchart("home")
        st.markdown(f"Team: {', '.join(config.TEAM)} · {config.CREDIT_LINE} · [GitHub]({config.REPO_URL})")
