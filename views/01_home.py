"""Page 1 — Home: the 30-second verdict (brief §8.1)."""
import streamlit as st

from src import config
from src import narrative as NR
from src import recommend as RC
from src import ui

ctx = ui.context()
s = st.session_state
ui.page_header("home", "Does 'safe' stay safe when the market crashes?",
               "We built a <b>high-risk</b> and a <b>low-risk</b> portfolio of Nifty 200 stocks today, then sent both back in time "
               "to real Indian market crises and calm spells to see whether the labels — and the weights — survive.")
left, right = ui.split()
A, B = ctx.P["A"], ctx.P["B"]
cr, cm, cur = ctx.crisis, ctx.calm, ctx.current
k = ctx.ck()

with left:
    st.markdown(f"**Your money:** {ui.inr(ctx.amount_a)} in Portfolio A and {ui.inr(ctx.amount_b)} in Portfolio B.")
    st.page_link(s["_pages"]["start"], label="Change amount", icon="✏️")
    c1, c2 = st.columns(2)
    for col, key, p, amt, kind, nm in ((c1, "A", A, ctx.amount_a, "a", "High risk — going for return"),
                                       (c2, "B", B, ctx.amount_b, "b", "Low risk — playing it safe")):
        with col:
            var_today = cur[key]["risk"]["Historical"][k]["var"]
            fall = cr[key]["replay"]["largest_fall"]
            ui.card(f"Portfolio {key} · {nm}",
                    ui.inr_short(amt),
                    f"{len(p['symbols'])} stocks · {len(p['industry_weights'])} industries<br>"
                    f"Expected return today: <b>{ui.pct(p['expected_return'])}</b> a year<br>"
                    f"A bad day today ({ctx.conf:.0%} VaR, {ctx.horizon}d): lose about <b>{ui.inr_short(ctx.h(var_today) * amt)}</b><br>"
                    f"In the {ctx.crisis_ev['name']}: fell as far as <b>{ui.inr_short(fall * amt)}</b>", kind)
    st.markdown("#### Three things we found")
    held = RC.label_holds(cr["A"], cr["B"])
    st.markdown(f"1. {NR.es_finding(ctx.crisis_ev['name'], cr['A'], cr['B'], ctx.amount_a, ctx.amount_b, held)}")
    st.markdown(f"2. {NR.replay_finding(ctx.crisis_ev['name'], cr['A'], cr['B'], cr['nifty'], ctx.amount_a, ctx.amount_b)}")
    boot = ctx.bootstrap()
    if boot:
        st.markdown(f"3. {NR.test2_finding(ctx.crisis_ev['name'], A, cr['A'], boot['A']['turnover_p95'], ctx.amount_a)}")
    else:
        t = cr["A"]["test2"]
        st.markdown(f"3. In the {ctx.crisis_ev['name']} the optimiser would have traded {ui.pct(t['turnover'], 0)} of Portfolio A "
                    f"({ui.inr_short(t['turnover'] * ctx.amount_a)}). Run the noise check on the Test #2 page to see if that is significant.")
    board = ctx.scoreboard()
    if board:
        n_held = sum(r["label_held"] for r in board)
        st.markdown(f"Across **all {len(board)} historical events** we tested, the high-risk label held in **{n_held}**.")
    st.markdown("#### How to explore")
    st.markdown("* **Change the past event** in the sidebar (COVID-19, 2008, taper tantrum …) — every page updates.\n"
                "* **Pick your own stocks** on *Pick stocks* — the app re-optimises in your browser.\n"
                "* **Flip “Show the Backing”** to see the maths behind every number, or hide it for the plain answer.")
    st.markdown("#### Team")
    st.markdown(f"{', '.join(config.TEAM)} · {config.CREDIT_LINE} · Financial Risk Analytics group project · "
                f"[GitHub repository]({config.REPO_URL})")

if right is not None:
    with right:
        st.markdown("#### The whole pipeline")
        ui.flowchart("home")
        st.markdown(
            f"* **Data:** {ctx.res['as_of']} snapshot of today's Nifty 200 — Yahoo Finance prices checked day-by-day against NSE's "
            "official closes, every split, bonus, rights issue and demerger rebuilt from NSE records.\n"
            "* **The call:** High risk = beta ≥ 1 and volatility above the median; Low risk = the opposite (trailing 3 years).\n"
            f"* **Weights:** A maximises the Sharpe ratio, B minimises variance — every weight between {config.W_MIN:.0%} and "
            f"{config.W_MAX:.0%}, no industry above {config.INDUSTRY_MAX:.0%}.\n"
            "* **Test #1:** Value at Risk and Expected Shortfall (four methods) in the current, crisis and calm windows.\n"
            "* **Test #2:** re-run Markowitz in each period for today's target return; compare against bootstrap noise.")
        st.markdown("#### Selected periods")
        for ev, kind in ((ctx.crisis_ev, "crisis"), (ctx.calm_ev, "calm")):
            st.html(f"<div class='ptm-card ptm-{kind}'><h4>{'🔴 Crisis' if kind == 'crisis' else '🟢 Calm'}: {ev['name']}</h4>"
                    f"<div class='sub'>{ev['label']}</div><p style='margin:.4rem 0 0'>{ev['story']}</p></div>")
