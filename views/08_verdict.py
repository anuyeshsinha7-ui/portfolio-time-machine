"""Page 8 — Verdict and recommendation (brief §8.8, §6.11)."""
import numpy as np
import pandas as pd
import streamlit as st

from src import charts as CH
from src import recommend as RC
from src import ui

ctx = ui.context()
s = st.session_state
left, right = ui.split()
board = ctx.scoreboard()
boot = ctx.bootstrap()
lv = RC.label_verdict(ctx.crisis, ctx.calm, board or [])
bv = RC.b_verdict(ctx.crisis, board or [])
TONE = {"Yes": "ok", "Partly": "mid", "No": "bad", "Robust": "ok", "Partly robust": "mid", "Regime-dependent": "bad"}
trig = RC.review_trigger(list(np.diff(np.log(ctx.crisis["nifty"]["value"]))))
mret = ui.nifty_close().pct_change().dropna()
now_vol = float(mret.iloc[-63:].std() * np.sqrt(252))

with left:
    ui.hero("Your answer", "Does 'safe' stay safe?",
            f"Tested on {len(board) if board else 'the chosen'} real market events since 2007", "")
    rows = [("🚀", "Is A really the bold one?",
             f"Riskier in the chosen crash: {'yes' if lv['crisis'] else 'no'} · calm year: {'yes' if lv['calm'] else 'no'}"
             + (f" · all events: {lv['events_held']}/{lv['events_total']}" if board else ""), ui.chip(lv["verdict"], TONE[lv["verdict"]]), ""),
            ("🛡️", "Did steady stay safe?",
             f"Beat the market in the chosen crash: {'yes' if bv['crisis'] else 'no'}"
             + (f" · in {bv['crises_held']} of {bv['crises_total']} crashes" if board else ""), ui.chip(bv["verdict"], TONE[bv["verdict"]]), "")]
    if boot:
        for key in ("A", "B"):
            rb = RC.robustness(ctx.crisis[key]["test2"]["turnover"], ctx.calm[key]["test2"]["turnover"], boot[key]["turnover_p95"])
            rows.append(("🔁", f"Are {key}'s weights robust?", "Would the optimiser really rebuild it in other times?",
                         ui.chip(rb["verdict"], TONE[rb["verdict"]]), ""))
    ui.list_rows(rows)
    ui.section("Which portfolio fits you?")
    opts = sorted({round(ctx.amount_a * f / 1000) * 1000 for f in [x / 100 for x in range(5, 81, 5)]})
    if s.get("tolerance") not in opts:
        s["tolerance"] = min(opts, key=lambda o: abs(o - 0.25 * ctx.amount_a))
    tol = st.select_slider("The biggest fall I could live with", options=opts, key="tolerance", format_func=ui.inr_short)
    f = RC.fit(tol, ctx.crisis["A"]["replay"]["largest_fall"], ctx.crisis["B"]["replay"]["largest_fall"], ctx.amount_a, ctx.amount_b)
    ui.compare(f"Worst fall in the {ui.short(ctx.crisis_ev)}", f["worst_A"], f["worst_B"], f"−{ui.inr_short(f['worst_A'])}",
               f"−{ui.inr_short(f['worst_B'])}", f"Your limit: −{ui.inr_short(tol)}")
    if f["pick"] == "A":
        ui.verdict("🚀", "Portfolio A fits you", f"Even in the crash its fall stayed within your {ui.inr_short(tol)}, and it expects the higher "
                   f"return ({ui.pct(ctx.P['A']['expected_return'])} a year vs {ui.pct(ctx.P['B']['expected_return'])}).")
    elif f["pick"] == "B":
        ui.verdict("🛡️", "Portfolio B fits you", f"A could fall {ui.inr_short(f['worst_A'])} in a crash like this — more than your "
                   f"{ui.inr_short(tol)}. B's worst was {ui.inr_short(f['worst_B'])}.")
    else:
        ui.verdict("✋", "Neither fits at this amount", f"To keep a crash like this within {ui.inr_short(tol)}, put at most "
                   f"<b>{ui.inr_short(f['max_amount_B'])}</b> in Portfolio B.")
    ui.section("When to check again")
    ui.note(f"Review your weights if the market's 3-month ups-and-downs rise above <b>{ui.pct(trig)}</b> (the calmest it got during the "
            f"crash). Today: <b>{ui.pct(now_vol)}</b> — {'time to review.' if now_vol > trig else 'all clear.'}",
            "🔔", "warn" if now_vol > trig else "good")
    ui.section("Good to know")
    ui.list_rows([("🕰️", "History isn't a promise", "Past crashes may not look like the next one.", "", ""),
                  ("🏆", "Today's winners only", "Companies that failed since 2007 aren't in the test, which flatters history.", "", ""),
                  ("💸", "Before costs and tax", "Brokerage, STT and capital-gains tax are not included.", "", ""),
                  ("🎓", "Educational project", "Not investment advice.", "", "")])

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
        st.markdown("#### Limitations")
        for t_, d_ in RC.LIMITATIONS:
            st.markdown(f"* **{t_}.** {d_}")
        if board:
            ui.show(CH.scoreboard_heatmap(board, ctx.amount_a, ctx.amount_b))
        st.graphviz_chart(f"""
digraph R {{ rankdir=TB; bgcolor="transparent"; node [shape=box, style="rounded,filled", fillcolor="#161D2C", color="#3A4560",
 fontname="Helvetica", fontsize=10]; edge [color="#6B7690", fontsize=9, fontname="Helvetica"];
 t [label="Your loss limit\\n{ui.inr(s.get('tolerance') or 0)}"]; a [label="A's worst crisis fall\\n≤ limit?"];
 b [label="B's worst crisis fall\\n≤ limit?"]; ra [label="Suggest A\\n(higher expected return)", fillcolor="#3A2420", color="#E8735A"];
 rb [label="Suggest B", fillcolor="#1C2C47", color="#3B7DD8"]; rn [label="Neither: cut the amount\\nto fit B"];
 t -> a; a -> ra [label="yes"]; a -> b [label="no"]; b -> rb [label="yes"]; b -> rn [label="no"]; }}""", width="stretch")
