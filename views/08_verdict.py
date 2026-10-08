"""Page 8 — Verdict and recommendation (brief §8.8, §6.11)."""
import numpy as np
import pandas as pd
import streamlit as st

from src import charts as CH
from src import recommend as RC
from src import ui

ctx = ui.context()
s = st.session_state
ui.page_header("verdict", "Verdict and recommendation",
               "Every sentence below is generated from the numbers by the rules shown in the Backing — change the stocks, the amount or "
               "the events and it rewrites itself.")
left, right = ui.split()
board = ctx.scoreboard()
boot = ctx.bootstrap()
lv = RC.label_verdict(ctx.crisis, ctx.calm, board or [])
bv = RC.b_verdict(ctx.crisis, board or [])
KIND = {"Yes": "ok", "Partly": "mid", "No": "bad", "Robust": "ok", "Partly robust": "mid", "Regime-dependent": "bad"}

with left:
    c1, c2 = st.columns(2)
    with c1:
        st.html(f"<div class='ptm-card ptm-a'><h4>Is A really high risk?</h4><div class='big'>{ui.pill(lv['verdict'], KIND[lv['verdict']])}</div>"
                f"<div class='sub'>Label held in the {ctx.crisis_ev['name']}: <b>{'yes' if lv['crisis'] else 'no'}</b>; "
                f"in the {ctx.calm_ev['name']}: <b>{'yes' if lv['calm'] else 'no'}</b>"
                + (f"; across all events: <b>{lv['events_held']} of {lv['events_total']}</b>" if board else "") + "</div></div>")
    with c2:
        st.html(f"<div class='ptm-card ptm-b'><h4>Did 'safe' stay safe?</h4><div class='big'>{ui.pill(bv['verdict'], KIND[bv['verdict']])}</div>"
                f"<div class='sub'>B beat the Nifty 50 (smaller ES and drawdown) in the {ctx.crisis_ev['name']}: "
                f"<b>{'yes' if bv['crisis'] else 'no'}</b>"
                + (f"; in <b>{bv['crises_held']} of {bv['crises_total']}</b> crises" if board else "") + "</div></div>")
    if boot:
        st.markdown("#### Are the weights robust?")
        cols = st.columns(2)
        for col, key in zip(cols, ("A", "B")):
            rb = RC.robustness(ctx.crisis[key]["test2"]["turnover"], ctx.calm[key]["test2"]["turnover"], boot[key]["turnover_p95"])
            col.html(f"<div class='ptm-card ptm-{key.lower()}'><h4>Portfolio {key}</h4><div class='big'>{ui.pill(rb['verdict'], KIND[rb['verdict']])}</div>"
                     f"<div class='sub'>Crisis turnover {ui.pct(ctx.crisis[key]['test2']['turnover'], 0)}, calm "
                     f"{ui.pct(ctx.calm[key]['test2']['turnover'], 0)}, noise limit {ui.pct(boot[key]['turnover_p95'], 0)}</div></div>")
    st.markdown(f"#### Worst case on your money ({ctx.crisis_ev['name']})")
    rows = []
    for key in ("A", "B"):
        amt = ctx.amount(key)
        r = ctx.crisis[key]
        rows.append((f"Portfolio {key}", ui.inr(amt), ui.inr(r["replay"]["low"] * amt), ui.inr(r["replay"]["largest_fall"] * amt),
                     ui.inr(ctx.h(r["risk"]["Historical"][ctx.ck()]["es"]) * amt)))
    st.dataframe(pd.DataFrame(rows, columns=["", "You invest", "Lowest value", "Largest fall",
                                             f"Average bad-day loss (ES {ctx.conf:.0%}, {ctx.horizon}d)"]),
                 hide_index=True, width="stretch")

    st.markdown("#### Which portfolio fits you?")
    default_tol = round(0.25 * ctx.amount_a / 10_000) * 10_000
    if "tol_txt" not in s:
        s["tol_txt"] = ui.inr(s.get("tolerance") or default_tol)
    tol_txt = st.text_input("The largest fall in value you could live with (₹)", key="tol_txt",
                            help="Think of the lowest point in a crash, before any recovery.")
    try:
        tol = ui.parse_amount(tol_txt)
        s["tolerance"] = tol
        f = RC.fit(tol, ctx.crisis["A"]["replay"]["largest_fall"], ctx.crisis["B"]["replay"]["largest_fall"],
                   ctx.amount_a, ctx.amount_b)
        if f["pick"] == "A":
            st.success(f"**Portfolio A fits.** Even in the {ctx.crisis_ev['name']} its worst fall ({ui.inr(f['worst_A'])}) stays within "
                       f"your {ui.inr(tol)}, and it expects the higher return ({ui.pct(ctx.P['A']['expected_return'])} vs "
                       f"{ui.pct(ctx.P['B']['expected_return'])}).")
        elif f["pick"] == "B":
            st.info(f"**Portfolio B fits; A does not.** A's worst fall was {ui.inr(f['worst_A'])} — more than your {ui.inr(tol)}. "
                    f"B's was {ui.inr(f['worst_B'])}.")
        else:
            st.warning(f"**Neither fits at this amount.** B's worst fall was {ui.inr(f['worst_B'])}. To keep B's crisis fall within "
                       f"{ui.inr(tol)}, invest at most **{ui.inr(f['max_amount_B'])}** in B.")
    except ui.AmountError as e:
        st.error(str(e))

    trig = RC.review_trigger(list(np.diff(np.log(ctx.crisis["nifty"]["value"]))))
    mret = ui.nifty_close().pct_change().dropna()
    now_vol = float(mret.iloc[-63:].std() * np.sqrt(252))
    st.markdown("#### When to look again")
    st.markdown(f"Revisit the weights if the Nifty 50's 3-month volatility rises above **{ui.pct(trig)}** — the calmest it got during "
                f"the {ctx.crisis_ev['name']}. Today it is **{ui.pct(now_vol)}** "
                f"({'above — review now' if now_vol > trig else 'below the trigger'}).")
    st.markdown("#### Limitations")
    for t_, d_ in RC.LIMITATIONS:
        st.markdown(f"* **{t_}.** {d_}")
    if board:
        st.markdown("#### All-events scoreboard")
        ui.show(CH.scoreboard_heatmap(board, ctx.amount_a, ctx.amount_b))
    elif st.button("Run the all-events scoreboard for your picks"):
        ui.compute_scoreboard(ctx)
        st.rerun()

if right is not None:
    with right:
        st.markdown("#### The rules behind every verdict")
        for name, rule in RC.RULES.items():
            st.markdown(f"* **{name.replace('_', ' ').capitalize()}.** {rule}")
        st.markdown("#### The numbers the rules used")
        rows = []
        for nm, reg, ev in ctx.regimes():
            rows.append({"Period": nm, "ES99 A": reg["A"]["risk"]["Historical"]["0.99"]["es"],
                         "ES99 B": reg["B"]["risk"]["Historical"]["0.99"]["es"], "Vol A": reg["A"]["volatility"],
                         "Vol B": reg["B"]["volatility"], "ES99 Nifty": reg["B"]["nifty"]["es99"],
                         "MDD B": reg["B"]["max_drawdown"], "MDD Nifty": reg["B"]["nifty"]["max_drawdown"],
                         "Label held": RC.label_holds(reg["A"], reg["B"]), "B beat Nifty": RC.b_held_up(reg["B"])})
        df = pd.DataFrame(rows)
        st.dataframe(df, hide_index=True, width="stretch",
                     column_config={c: st.column_config.NumberColumn(format="percent") for c in df.columns[1:8]})
        st.markdown("#### Recommendation logic")
        st.graphviz_chart(f"""
digraph R {{ rankdir=TB; bgcolor="transparent"; node [shape=box, style="rounded,filled", fillcolor="#FFFFFF", color="#C9CED8",
 fontname="Helvetica", fontsize=10]; edge [color="#9AA1AE", fontsize=9, fontname="Helvetica"];
 t [label="Your loss limit\\n{ui.inr(s.get('tolerance') or 0)}"]; a [label="A's worst crisis fall\\n≤ limit?"];
 b [label="B's worst crisis fall\\n≤ limit?"]; ra [label="Suggest A\\n(higher expected return)", fillcolor="#FCE9E4", color="#E8735A"];
 rb [label="Suggest B", fillcolor="#E3EDFB", color="#3B7DD8"]; rn [label="Neither: cut the amount\\nto fit B"];
 t -> a; a -> ra [label="yes"]; a -> b [label="no"]; b -> rb [label="yes"]; b -> rn [label="no"]; }}""", width="stretch")
